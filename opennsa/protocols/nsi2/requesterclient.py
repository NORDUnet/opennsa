"""
Web Service protocol for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from twisted.python import log, failure
from twisted.web.error import Error as WebError

from opennsa import error
from opennsa.protocols.shared import minisoap, httpclient

from opennsa.protocols.nsi2 import connectiontypes as CT, headertypes as HT, actions, helper




def utcTime(dt):
    return dt.isoformat().rsplit('.',1)[0] + 'Z'



class RequesterClient:

    def __init__(self, reply_to, ctx_factory=None):

        self.reply_to = reply_to
        self.ctx_factory = ctx_factory


    def _createGenericRequestType(self, message_name, correlation_id, requester_nsa, provider_nsa, connection_id):

        header_payload = helper.createHeader(correlation_id, requester_nsa.urn(), provider_nsa.urn(), self.reply_to)

        request = CT.GenericRequestType(connection_id)
        body_payload = helper.export(request, message_name)

        payload = minisoap.createSoapPayload(body_payload, header_payload)

        return payload


    def _handleErrorReply(self, err):

        # is this isn't a web error we cannot do anything about it here
        if err.check(WebError) is None:
            return err

        if err.value.status != '500':
            log.msg("Got error with non-500 status. Message: %s" % err.getErrorMessage())
            return err

        payload = err.value.response

        fault_code, fault_string, detail = minisoap.parseFault(payload)

        service_exception = None
        if detail:
            service_exception = CT.parseString(detail, CT.ServiceExceptionType)

        if service_exception is None:
            # this is not entirely correct, but it isn't really wrong either
            ex = error.InternalServerError(fault_string)
        else:
            ext = error.lookup(service_exception.errorId)
            ex = ext(service_exception.text)

        err = failure.Failure(ex)

        return err


    def reserve(self, service_url, correlation_id, requester_nsa, provider_nsa, session_security_attr,
                global_reservation_id, description, connection_id, service_parameters):

        header_payload = helper.createHeader(correlation_id, requester_nsa.urn(), provider_nsa.urn(), self.reply_to)

        sp = service_parameters
        s_stp = sp.source_stp
        d_stp = sp.dest_stp

        if sp.start_time.utcoffset() is None:
            raise ValueError('Start time has no time zone info')
        if sp.end_time.utcoffset() is None:
            raise ValueError('End time has no time zone info')

        schedule = CT.ScheduleType(sp.start_time.isoformat(), sp.end_time.isoformat())
        service_attributes = None

        # EROs not supported, need to use TypeValuePairListType for labels
        source_stp = CT.StpType(s_stp.network, s_stp.endpoint, None, 'Ingress')
        dest_stp   = CT.StpType(d_stp.network, d_stp.endpoint, None, 'Egress')
        path = CT.PathType(sp.directionality, None, source_stp, dest_stp)

        criteria = CT.ReservationRequestCriteriaType(schedule, sp.bandwidth, service_attributes, path)

        reservation = CT.ReserveType(global_reservation_id, description, connection_id, criteria)

        # create payload
        body_payload   = helper.export(reservation, 'reserve')
        payload = minisoap.createSoapPayload(body_payload, header_payload)

        def gotReply(data):
            log.msg(' -- Received Response Payload --\n' + data + '\n -- END. Received Response Payload --', payload=True)

        f = httpclient.httpRequest(provider_nsa.url(), actions.RESERVE, payload, ctx_factory=self.ctx_factory)
        f.deferred.addCallbacks(gotReply, self._handleErrorReply)
        return f.deferred


    def provision(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id):

        payload = self._createGenericRequestType('provision', correlation_id, requester_nsa, provider_nsa, connection_id)

        def gotReply(data):
            log.msg(' -- START: Provision Response --\n' + data + '\n -- END. Provision Response --', payload=True)

        f = httpclient.httpRequest(provider_nsa.url(), actions.PROVISION, payload, ctx_factory=self.ctx_factory)
        f.deferred.addCallbacks(gotReply, self._handleErrorReply)
        return f.deferred


    def release(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id):

        def gotReply(data):
            log.msg(' -- START: Release Response --\n' + data + '\n -- END. Release Response --', payload=True)

        payload = self._createGenericRequestType('release', correlation_id, requester_nsa, provider_nsa, connection_id)
        f = httpclient.httpRequest(provider_nsa.url(), actions.RELEASE, payload, ctx_factory=self.ctx_factory)
        f.deferred.addCallbacks(gotReply, self._handleErrorReply)
        return f.deferred


    def terminate(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id):

        def gotReply(data):
            log.msg(' -- START: Terminate Response --\n' + data + '\n -- END. Terminate Response --', payload=True)

        payload = self._createGenericRequestType('terminate', correlation_id, requester_nsa, provider_nsa, connection_id)
        f = httpclient.httpRequest(provider_nsa.url(), actions.TERMINATE, payload, ctx_factory=self.ctx_factory)
        f.deferred.addCallbacks(gotReply, self._handleErrorReply)
        return f.deferred


    def query(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, operation="Summary", connection_ids=None, global_reservation_ids=None):

        req = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}QueryType')
        #print req

        req.requesterNSA = requester_nsa.urn()
        req.providerNSA  = provider_nsa.urn()
        req.operation = operation
        req.queryFilter.connectionId = connection_ids or []
        req.queryFilter.globalReservationId = global_reservation_ids or []
        #print req

        d = self.client.invoke(provider_nsa.url(), 'query', correlation_id, self.reply_to, req)
        return d

