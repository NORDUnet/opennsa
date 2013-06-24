"""
Web Service protocol for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from opennsa import nsa
from opennsa.protocols.shared import minisoap, httpclient
from opennsa.protocols.nsi2 import actions, bindings, helper



def utcTime(dt):
    return dt.isoformat().rsplit('.',1)[0] + 'Z'



class ProviderClient:

    def __init__(self, ctx_factory=None):

        self.ctx_factory = ctx_factory


    def _genericConfirm(self, element_name, requester_url, action, correlation_id, requester_nsa, provider_nsa, connection_id):

        header_element = helper.createHeader(requester_nsa, provider_nsa, correlation_id=correlation_id)

        confirm = bindings.GenericConfirmedType(connection_id)
        body_element   = confirm.xml(element_name)

        payload = minisoap.createSoapPayload(body_element, header_element)

        def gotReply(data):
            # for now we just ignore this, as long as we get an okay
            return

        d = httpclient.soapRequest(requester_url, action, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(gotReply) #, errReply)
        return d


    def _genericFailure(self, requester_url, action, message_name, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, err):

        header_payload = helper.createHeader(correlation_id, requester_nsa, provider_nsa)

        connection_states = bindings.ConnectionStatesType(bindings.ReservationStateType(0, 'TerminateFailed'),
                                                    bindings.ProvisionStateType(0,   'TerminateFailed'),
                                                    bindings.ActivationStateType(0,  'Inactive'))

        se = helper.createServiceException(err, provider_nsa)

        generic_failed = bindings.GenericFailedType(global_reservation_id, connection_id, connection_states, se)

        body_payload   = helper.export(generic_failed, message_name)

        payload = minisoap.createSoapPayload(body_payload, header_payload)

        def gotReply(data):
            # for now we just ignore this, as long as we get an okay
            return

        d = httpclient.soapRequest(requester_url, action, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(gotReply) #, errReply)
        return d


    def reserveConfirmed(self, nsi_header, connection_id, global_reservation_id, description, service_parameters):

        header_element = helper.createHeader(nsi_header.requester_nsa, nsi_header.provider_nsa, correlation_id=nsi_header.correlation_id)

        sp = service_parameters

        version = 0
        schedule = bindings.ScheduleType( sp.start_time.isoformat(), sp.end_time.isoformat() )
        bandwidth = sp.bandwidth

        service_attributes = None

        src_stp = helper.createSTPType(sp.source_stp)
        dst_stp = helper.createSTPType(sp.dest_stp)

        path = bindings.PathType(sp.directionality, False, src_stp, dst_stp, None)

        criteria = bindings.ReservationConfirmCriteriaType(version, schedule, bandwidth, service_attributes, path)

        reserve_conf = bindings.ReserveConfirmedType(connection_id, global_reservation_id, description, [ criteria ] )

        body_element = reserve_conf.xml(bindings.reserveConfirmed)
        payload = minisoap.createSoapPayload(body_element, header_element)

        def gotReply(data):
            # we don't really do anything about these
            return ""

        d = httpclient.soapRequest(nsi_header.reply_to, actions.RESERVE_CONFIRMED, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(gotReply) #, errReply)
        return d


    def reserveFailed(self, requester_url, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, err):

        return self._genericFailure(requester_url, actions.RESERVE_FAILED, 'reserveFailed',
                                    correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, err)


    def reserveCommitConfirmed(self, requester_url, requester_nsa, provider_nsa, correlation_id, connection_id):

        return self._genericConfirm(bindings.reserveCommitConfirmed, requester_url, actions.RESERVE_COMMIT_CONFIRMED,
                                    correlation_id, requester_nsa, provider_nsa, connection_id)


    def provisionConfirmed(self, requester_url, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id):

        return self._genericConfirm(bindings.provisionConfirmed, requester_url, actions.PROVISION_CONFIRMED,
                                    correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id)


    def provisionFailed(self, requester_url, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, err):

        return self._genericFailure(requester_url, actions.PROVISION_FAILED, 'provisionFailed',
                                    correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, err)


    def releaseConfirmed(self, requester_url, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id):

        return self._genericConfirm('releaseConfirmed', requester_url, actions.RELEASE_CONFIRMED,
                                    correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id)

    def releaseFailed(self, requester_url, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, err):

        return self._genericFailure(requester_url, actions.RELEASE_FAILED, 'releaseFailed',
                                    correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, err)


    def terminateConfirmed(self, requester_url, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id):

        return self._genericConfirm('terminateConfirmed', requester_url, actions.TERMINATE_CONFIRMED,
                                    correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id)


    def terminateFailed(self, requester_url, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, err):

        return self._genericFailure(requester_url, actions.TERMINATE_FAILED, 'terminateFailed',
                                    correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, err)


    def queryConfirmed(self, requester_url, correlation_id, requester_nsa, provider_nsa, operation, connections):

        assert operation == 'Summary', 'Only Summary operation supported in nsi2.queryConfirmed so far'

        conns = []
        for conn in connections:
            # need to create criteria here sometime
            criteria      = None
            states        = bindings.ConnectionStatesType( bindings.ReservationStateType(0, conn.state()),
                                                     bindings.ProvisionStateType(  0, conn.state()),
                                                     bindings.ActivationStateType( 0, conn.state()))
            children      = None
            conns.append( bindings.QuerySummaryResultType(conn.global_reservation_id, conn.description, conn.connection_id,
                                                    criteria, conn.requester_nsa, states, children) )

        query_confirmed = bindings.QueryConfirmedType(reservationSummary=conns)

        # --

        header_payload = helper.createHeader(correlation_id, requester_nsa, provider_nsa)
        body_payload   = helper.export(query_confirmed, 'queryConfirmed')

        payload = minisoap.createSoapPayload(body_payload, header_payload)

        def gotReply(data):
            # we don't really do anything about these
            return ""

        d = httpclient.soapRequest(requester_url, actions.QUERY_CONFIRMED, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(gotReply) #, errReply)
        return d

#        if operation == "Summary":
#            qsrs = []
#            for conn in connections:
#                qsr = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}QuerySummaryResultType')
#                #print qsr
#                qsr.globalReservationId = conn.global_reservation_id
#                qsr.description         = conn.description
#                qsr.connectionId        = conn.connection_id
#                qsr.connectionState     = conn.state()
#
#                qsr.path.sourceSTP.stpId    = conn.source_stp.urn()
#                qsr.path.destSTP.stpId      = conn.dest_stp.urn()
#
#                qsr.serviceParameters.schedule.startTime = utcTime(conn.service_parameters.start_time)
#                qsr.serviceParameters.schedule.endTime   = utcTime(conn.service_parameters.end_time)
#
#                qsr.serviceParameters.bandwidth.desired  = conn.service_parameters.bandwidth.desired
#                qsr.serviceParameters.bandwidth.minimum  = conn.service_parameters.bandwidth.minimum
#                qsr.serviceParameters.bandwidth.maximum  = conn.service_parameters.bandwidth.maximum
#
#                def createOrderedSTP(stp, rank):
#                    ostp = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}OrderedServiceTerminationPointType')
#                    ostp.stpId = stp.urn()
#                    ostp._order = rank
#                    return ostp
#
#                # create list of all stps, but skip source and dest stp
#                stps = [ stp for sc in conn.connections() for stp in sc.stps() ] [1:-1]
#                for i, stp in zip(range(len(stps)), stps):
#                    qsr.path.stpList.stp.append( createOrderedSTP(stp, i) )
#
#                qsrs.append(qsr)
#
#            res.reservationSummary = qsrs
#
#        elif operation == "Details":
#            qdr = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}QueryDetailsResultType')
#            #print qdr
#            qdr.globalReservationId = '123'
#            res.reservationDetails = [ qdr ]
#
#        else:
#            raise ValueError('Invalid query operation type')
#
#        d = self.client.invoke(requester_url, 'queryConfirmed', correlation_id, res)
#        return d
#
#
#    def queryFailed(self, requester_url, correlation_id, requester_nsa, provider_nsa, error_msg):
#
#        print "CLIENT QUERY FAILED"
#        qft = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}QueryFailedType')
#        net = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}ServiceExceptionType')
#
#        qft.requesterNSA = requester_nsa
#        qft.providerNSA  = provider_nsa
#
#        net.errorId = 'QUERY_FAILURE'
#        net.text = error_msg
#        qft.serviceException = net
#
#        d = self.client.invoke(requester_url, 'queryFailed', correlation_id, qft)
#        return d

