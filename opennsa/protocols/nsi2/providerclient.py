"""
Web Service protocol for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2013)
"""

from opennsa.protocols.shared import minisoap, httpclient
from opennsa.protocols.nsi2 import actions, bindings, helper



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


    def _genericFailure(self, requester_url, action, message_name, requester_nsa, provider_nsa, correlation_id,
                        connection_id, connection_states, err):

        header_element = helper.createHeader(requester_nsa, provider_nsa, correlation_id=correlation_id)

        active, version, consistent = connection_states[3]
        data_plane_state = bindings.DataPlaneStatusType(active, version, consistent)
        connection_states = bindings.ConnectionStatesType(connection_states[0], connection_states[1], connection_states[2], data_plane_state)

        se = helper.createServiceException(err, provider_nsa)

        failure = bindings.GenericFailedType(connection_id, connection_states, se)

        body_element = failure.xml(message_name)

        payload = minisoap.createSoapPayload(body_element, header_element)

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
        schedule = bindings.ScheduleType( helper.createXMLTime(sp.start_time) ,helper.createXMLTime(sp.end_time) )
        bandwidth = sp.bandwidth

        service_attributes = None

        src_stp = helper.createSTPType(sp.source_stp)
        dst_stp = helper.createSTPType(sp.dest_stp)

        path = bindings.PathType(sp.directionality, False, src_stp, dst_stp, None)

        criteria = bindings.ReservationConfirmCriteriaType(version, schedule, bandwidth, service_attributes, path)

        reserve_conf = bindings.ReserveConfirmedType(connection_id, global_reservation_id, description, criteria )

        body_element = reserve_conf.xml(bindings.reserveConfirmed)
        payload = minisoap.createSoapPayload(body_element, header_element)

        def gotReply(data):
            # we don't really do anything about these
            return ""

        d = httpclient.soapRequest(nsi_header.reply_to, actions.RESERVE_CONFIRMED, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(gotReply) #, errReply)
        return d


    def reserveFailed(self, requester_url, requester_nsa, provider_nsa, correlation_id, connection_id, connection_states, err):

        return self._genericFailure(requester_url, actions.RESERVE_FAILED, bindings.reserveFailed,
                                    requester_nsa, provider_nsa, correlation_id,
                                    connection_id, connection_states, err)


    def reserveCommitConfirmed(self, requester_url, requester_nsa, provider_nsa, correlation_id, connection_id):

        return self._genericConfirm(bindings.reserveCommitConfirmed, requester_url, actions.RESERVE_COMMIT_CONFIRMED,
                                    correlation_id, requester_nsa, provider_nsa, connection_id)


    def reserveCommitFailed(self, requester_url, requester_nsa, provider_nsa, correlation_id, connection_id, connection_states, err):

        return self._genericFailure(requester_url, actions.RESERVE_COMMIT_FAILED, bindings.reserveCommitFailed,
                                    requester_nsa, provider_nsa, correlation_id, connection_id, connection_states, err)


    def reserveAbortConfirmed(self, requester_url, requester_nsa, provider_nsa, correlation_id, connection_id):

        return self._genericConfirm(bindings.reserveAbortConfirmed, requester_url, actions.RESERVE_ABORT_CONFIRMED,
                                    correlation_id, requester_nsa, provider_nsa, connection_id)


    def reserveAbortFailed(self, requester_url, requester_nsa, provider_nsa, correlation_id, connection_id, connection_states, err):

        return self._genericFailure(requester_url, actions.RESERVE_ABORT_FAILED, bindings.reserveAbortFailed,
                                    requester_nsa, provider_nsa, correlation_id, connection_id, connection_states, err)


    def provisionConfirmed(self, requester_url, correlation_id, requester_nsa, provider_nsa, connection_id):

        return self._genericConfirm(bindings.provisionConfirmed, requester_url, actions.PROVISION_CONFIRMED,
                                    correlation_id, requester_nsa, provider_nsa, connection_id)


    def releaseConfirmed(self, requester_url, correlation_id, requester_nsa, provider_nsa, connection_id):

        return self._genericConfirm(bindings.releaseConfirmed, requester_url, actions.RELEASE_CONFIRMED,
                                    correlation_id, requester_nsa, provider_nsa, connection_id)


    def terminateConfirmed(self, requester_url, correlation_id, requester_nsa, provider_nsa, connection_id):

        return self._genericConfirm(bindings.terminateConfirmed, requester_url, actions.TERMINATE_CONFIRMED,
                                    correlation_id, requester_nsa, provider_nsa, connection_id)

    # notifications

    def reserveTimeout(self, requester_url, requester_nsa, provider_nsa, connection_id, notification_id, timestamp, timeout_value, originating_connection_id, originating_nsa):

        header_element = helper.createHeader(requester_nsa, provider_nsa)

        reserve_timeout = bindings.ReserveTimeoutRequestType(connection_id, notification_id, timestamp, timeout_value, originating_connection_id, originating_nsa)

        body_element = reserve_timeout.xml(bindings.reserveTimeout)

        payload = minisoap.createSoapPayload(body_element, header_element)

        d = httpclient.soapRequest(requester_url, actions.RESERVE_TIMEOUT, payload, ctx_factory=self.ctx_factory)
        return d


    def dataPlaneStateChange(self, requester_url, requester_nsa, provider_nsa, connection_id, notification_id, timestamp, active, version, consistent):

        header_element = helper.createHeader(requester_nsa, provider_nsa)

        data_plane_status = bindings.DataPlaneStatusType(active, version, consistent)
        dps = bindings.DataPlaneStateChangeRequestType(connection_id, notification_id, timestamp, data_plane_status)

        body_element = dps.xml(bindings.dataPlaneStateChange)

        payload = minisoap.createSoapPayload(body_element, header_element)

        d = httpclient.soapRequest(requester_url, actions.DATA_PLANE_STATE_CHANGE, payload, ctx_factory=self.ctx_factory)
        return d


    def errorEvent(self, requester_url, requester_nsa, provider_nsa, connection_id, notification_id, timestamp, event, info, service_ex):

        header_element = helper.createHeader(requester_nsa, provider_nsa)

        if service_ex:
            nsa_id, connection_id, error_id, text, variables, child_ex = service_ex
            service_exception = bindings.ServiceExceptionType(nsa_id, connection_id, error_id, text, None, None)
        else:
            service_exception = None

        error_event = bindings.ErrorEventType(connection_id, notification_id, timestamp, event, None, service_exception)

        body_element = error_event.xml(bindings.errorEvent)

        payload = minisoap.createSoapPayload(body_element, header_element)

        d = httpclient.soapRequest(requester_url, actions.ERROR_EVENT, payload, ctx_factory=self.ctx_factory)
        return d


    def querySummaryConfirmed(self, requester_url, requester_nsa, provider_nsa, correlation_id, reservations):

        query_results = []

        for rsv in reservations:

            cid, gid, desc, crits, req_nsa, states, nid = rsv
            rsm, psm, lsm, dsm = states

            criterias = []
            for crit in crits:
                schedule   = bindings.ScheduleType(crit.start_time, crit.end_time)
                source_stp = helper.createSTPType(crit.source_stp)
                dest_stp   = helper.createSTPType(crit.dest_stp)
                path       = bindings.PathType('Bidirectional', False, source_stp, dest_stp, None)
                criteria   = bindings.QuerySummaryResultCriteriaType(crit.version, schedule, crit.bandwidth, None, path, None)
                criterias.append(criteria)

            data_plane_status = bindings.DataPlaneStatusType(dsm[0], dsm[1], dsm[2])
            connection_states = bindings.ConnectionStatesType(rsm, psm, lsm, data_plane_status)

            qsrt = bindings.QuerySummaryResultType(cid, gid, desc, criterias, req_nsa, connection_states, nid)
            query_results.append(qsrt)

        # --

        header_element = helper.createHeader(requester_nsa, provider_nsa)

        query_confirmed = bindings.QuerySummaryConfirmedType(query_results)
        body_element    = query_confirmed.xml(bindings.querySummaryConfirmed)

        payload = minisoap.createSoapPayload(body_element, header_element)

        d = httpclient.soapRequest(requester_url, actions.QUERY_SUMMARY_CONFIRMED, payload, ctx_factory=self.ctx_factory)
        return d


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

