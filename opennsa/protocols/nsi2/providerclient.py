"""
Web Service protocol for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2013)
"""

from opennsa.protocols.shared import minisoap, httpclient
from opennsa.protocols.nsi2 import helper
from opennsa.protocols.nsi2.bindings import actions, nsiconnection, p2pservices



class ProviderClient:

    def __init__(self, ctx_factory=None):

        self.ctx_factory = ctx_factory


    def _genericConfirm(self, element_name, requester_url, action, correlation_id, requester_nsa, provider_nsa, connection_id):

        header_element = helper.createHeader(requester_nsa, provider_nsa, correlation_id=correlation_id)

        confirm = nsiconnection.GenericConfirmedType(connection_id)
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
        data_plane_state = nsiconnection.DataPlaneStatusType(active, version, consistent)
        connection_states = nsiconnection.ConnectionStatesType(connection_states[0], connection_states[1], connection_states[2], data_plane_state)

        se = helper.createServiceException(err, provider_nsa)

        failure = nsiconnection.GenericFailedType(connection_id, connection_states, se)

        body_element = failure.xml(message_name)

        payload = minisoap.createSoapPayload(body_element, header_element)

        def gotReply(data):
            # for now we just ignore this, as long as we get an okay
            return

        d = httpclient.soapRequest(requester_url, action, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(gotReply) #, errReply)
        return d


    def reserveConfirmed(self, nsi_header, connection_id, global_reservation_id, description, criteria):

        header_element = helper.createHeader(nsi_header.requester_nsa, nsi_header.provider_nsa, correlation_id=nsi_header.correlation_id)

        schedule = nsiconnection.ScheduleType( helper.createXMLTime(criteria.schedule.start_time) ,helper.createXMLTime(criteria.schedule.end_time) )

        sd = criteria.service_def

        # we only support evts for now
        src_stp = helper.createSTPType(sd.source_stp)
        dst_stp = helper.createSTPType(sd.dest_stp)
        src_stp.labels = []
        dst_stp.labels = []

        src_vlan = sd.source_stp.labels[0].labelValue()
        dst_vlan = sd.dest_stp.labels[0].labelValue()
 
        evts = p2pservices.EthernetVlanType(src_stp, dst_stp, src_vlan, dst_vlan, sd.mtu, sd.burst_size, sd.capacity, sd.directionality, sd.symmetric, None)

        criteria = nsiconnection.ReservationConfirmCriteriaType(criteria.revision, schedule, str(p2pservices.evts), { p2pservices.evts : evts } )

        reserve_conf = nsiconnection.ReserveConfirmedType(connection_id, global_reservation_id, description, criteria)

        body_element = reserve_conf.xml(nsiconnection.reserveConfirmed)
        payload = minisoap.createSoapPayload(body_element, header_element)

        def gotReply(data):
            # we don't really do anything about these
            return ""

        d = httpclient.soapRequest(nsi_header.reply_to, actions.RESERVE_CONFIRMED, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(gotReply) #, errReply)
        return d


    def reserveFailed(self, requester_url, requester_nsa, provider_nsa, correlation_id, connection_id, connection_states, err):

        return self._genericFailure(requester_url, actions.RESERVE_FAILED, nsiconnection.reserveFailed,
                                    requester_nsa, provider_nsa, correlation_id,
                                    connection_id, connection_states, err)


    def reserveCommitConfirmed(self, requester_url, requester_nsa, provider_nsa, correlation_id, connection_id):

        return self._genericConfirm(nsiconnection.reserveCommitConfirmed, requester_url, actions.RESERVE_COMMIT_CONFIRMED,
                                    correlation_id, requester_nsa, provider_nsa, connection_id)


    def reserveCommitFailed(self, requester_url, requester_nsa, provider_nsa, correlation_id, connection_id, connection_states, err):

        return self._genericFailure(requester_url, actions.RESERVE_COMMIT_FAILED, nsiconnection.reserveCommitFailed,
                                    requester_nsa, provider_nsa, correlation_id, connection_id, connection_states, err)


    def reserveAbortConfirmed(self, requester_url, requester_nsa, provider_nsa, correlation_id, connection_id):

        return self._genericConfirm(nsiconnection.reserveAbortConfirmed, requester_url, actions.RESERVE_ABORT_CONFIRMED,
                                    correlation_id, requester_nsa, provider_nsa, connection_id)


    def reserveAbortFailed(self, requester_url, requester_nsa, provider_nsa, correlation_id, connection_id, connection_states, err):

        return self._genericFailure(requester_url, actions.RESERVE_ABORT_FAILED, nsiconnection.reserveAbortFailed,
                                    requester_nsa, provider_nsa, correlation_id, connection_id, connection_states, err)


    def provisionConfirmed(self, requester_url, correlation_id, requester_nsa, provider_nsa, connection_id):

        return self._genericConfirm(nsiconnection.provisionConfirmed, requester_url, actions.PROVISION_CONFIRMED,
                                    correlation_id, requester_nsa, provider_nsa, connection_id)


    def releaseConfirmed(self, requester_url, correlation_id, requester_nsa, provider_nsa, connection_id):

        return self._genericConfirm(nsiconnection.releaseConfirmed, requester_url, actions.RELEASE_CONFIRMED,
                                    correlation_id, requester_nsa, provider_nsa, connection_id)


    def terminateConfirmed(self, requester_url, correlation_id, requester_nsa, provider_nsa, connection_id):

        return self._genericConfirm(nsiconnection.terminateConfirmed, requester_url, actions.TERMINATE_CONFIRMED,
                                    correlation_id, requester_nsa, provider_nsa, connection_id)

    # notifications

    def reserveTimeout(self, requester_url, requester_nsa, provider_nsa, correlation_id,
                       connection_id, notification_id, timestamp, timeout_value, originating_connection_id, originating_nsa):

        header_element = helper.createHeader(requester_nsa, provider_nsa, correlation_id=correlation_id)

        reserve_timeout = nsiconnection.ReserveTimeoutRequestType(connection_id, notification_id, helper.createXMLTime(timestamp), timeout_value, originating_connection_id, originating_nsa)

        body_element = reserve_timeout.xml(nsiconnection.reserveTimeout)

        payload = minisoap.createSoapPayload(body_element, header_element)

        d = httpclient.soapRequest(requester_url, actions.RESERVE_TIMEOUT, payload, ctx_factory=self.ctx_factory)
        return d


    def dataPlaneStateChange(self, requester_url, requester_nsa, provider_nsa, correlation_id,
                             connection_id, notification_id, timestamp, active, version, consistent):

        header_element = helper.createHeader(requester_nsa, provider_nsa, correlation_id=correlation_id)

        data_plane_status = nsiconnection.DataPlaneStatusType(active, version, consistent)
        dps = nsiconnection.DataPlaneStateChangeRequestType(connection_id, notification_id, helper.createXMLTime(timestamp), data_plane_status)

        body_element = dps.xml(nsiconnection.dataPlaneStateChange)

        payload = minisoap.createSoapPayload(body_element, header_element)

        d = httpclient.soapRequest(requester_url, actions.DATA_PLANE_STATE_CHANGE, payload, ctx_factory=self.ctx_factory)
        return d


    def errorEvent(self, requester_url, requester_nsa, provider_nsa, correlation_id,
                   connection_id, notification_id, timestamp, event, info, service_ex):

        header_element = helper.createHeader(requester_nsa, provider_nsa, correlation_id=correlation_id)

        if service_ex:
            nsa_id, connection_id, error_id, text, variables, child_ex = service_ex
            service_exception = nsiconnection.ServiceExceptionType(nsa_id, connection_id, error_id, text, None, None)
        else:
            service_exception = None

        error_event = nsiconnection.ErrorEventType(connection_id, notification_id, helper.createXMLTime(timestamp), event, None, service_exception)

        body_element = error_event.xml(nsiconnection.errorEvent)

        payload = minisoap.createSoapPayload(body_element, header_element)

        d = httpclient.soapRequest(requester_url, actions.ERROR_EVENT, payload, ctx_factory=self.ctx_factory)
        return d


    def querySummaryConfirmed(self, requester_url, requester_nsa, provider_nsa, correlation_id, reservations):

        header_element = helper.createHeader(requester_nsa, provider_nsa, correlation_id=correlation_id)

        query_summary_result = helper.buildQuerySummaryResultType(reservations)
        qsr_elements = [ qsr.xml(nsiconnection.reservation) for qsr in query_summary_result ]

        payload = minisoap.createSoapPayload(qsr_elements, header_element)

        d = httpclient.soapRequest(requester_url, actions.QUERY_SUMMARY_CONFIRMED, payload, ctx_factory=self.ctx_factory)
        return d


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

