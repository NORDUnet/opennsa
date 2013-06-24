"""
Web Service protocol for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from twisted.python import log, failure
from twisted.web.error import Error as WebError

from opennsa import error
from opennsa.protocols.shared import minisoap, httpclient

from opennsa.protocols.nsi2 import actions, bindings, helper


URN_NETWORK = 'urn:ogf:network:'


def utcTime(dt):
    return dt.isoformat().rsplit('.',1)[0] + 'Z'



class RequesterClient:

    def __init__(self, reply_to, ctx_factory=None):

        self.reply_to = reply_to
        self.ctx_factory = ctx_factory


    def _createGenericRequestType(self, message_name, correlation_id, requester_nsa, provider_nsa, connection_id):

        header_payload = helper.createHeader(correlation_id, requester_nsa.urn(), provider_nsa.urn(), self.reply_to)

        request = bindings.GenericRequestType(connection_id)
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

        fault_code, fault_string, detail = minisoap.parseFault(err.value.response)

        service_exception = None
        if detail:
            service_exception = bindings.parseString(detail, bindings.ServiceExceptionType)

        if service_exception is None:
            # this is not entirely correct, but it isn't really wrong either
            ex = error.InternalServerError(fault_string)
        else:
            ext = error.lookup(service_exception.errorId)
            ex = ext(service_exception.text)

        err = failure.Failure(ex)

        return err


    def reserve(self, service_url, correlation_id, requester_nsa, provider_nsa, session_security_attr,
                global_reservation_id, description, connection_id, version, service_parameters):

        header_payload = helper.createHeader(requester_nsa.urn(), provider_nsa.urn(), reply_to=self.reply_to, correlation_id=correlation_id)

        sp = service_parameters

        if sp.start_time.utcoffset() is None:
            raise ValueError('Start time has no time zone info')
        if sp.end_time.utcoffset() is None:
            raise ValueError('End time has no time zone info')

        schedule = bindings.ScheduleType(sp.start_time.isoformat(), sp.end_time.isoformat())
        service_attributes = None

        symmetric = False

        src_stp = helper.createSTPType(sp.source_stp)
        dst_stp = helper.createSTPType(sp.dest_stp)

        path = bindings.PathType(sp.directionality, symmetric, src_stp, dst_stp, None)

        criteria = bindings.ReservationRequestCriteriaType(version, schedule, sp.bandwidth, service_attributes, path)

        reservation = bindings.ReserveType(global_reservation_id, description, connection_id, criteria)

        body_payload   = reservation.xml(bindings.reserve)
        payload = minisoap.createSoapPayload(body_payload, header_payload)

        def gotReply(data):
            pass

        d = httpclient.soapRequest(provider_nsa.endpoint, actions.RESERVE, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(gotReply, self._handleErrorReply)
        return d


    def provision(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id):

        payload = self._createGenericRequestType('provision', correlation_id, requester_nsa, provider_nsa, connection_id)

        def gotReply(data):
            pass

        d = httpclient.soapRequest(provider_nsa.endpoint, actions.PROVISION, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(gotReply, self._handleErrorReply)
        return d


    def release(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id):

        def gotReply(data):
            pass

        payload = self._createGenericRequestType('release', correlation_id, requester_nsa, provider_nsa, connection_id)
        d = httpclient.soapRequest(provider_nsa.endpoint, actions.RELEASE, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(gotReply, self._handleErrorReply)
        return d


    def terminate(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id):

        def gotReply(data):
            pass

        payload = self._createGenericRequestType('terminate', correlation_id, requester_nsa, provider_nsa, connection_id)
        d = httpclient.soapRequest(provider_nsa.endpoint, actions.TERMINATE, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(gotReply, self._handleErrorReply)
        return d


    def query(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, operation="Summary", connection_ids=None, global_reservation_ids=None):

        header_payload = helper.createHeader(correlation_id, requester_nsa.urn(), provider_nsa.urn(), self.reply_to)

        filter_ = bindings.QueryFilterType(connection_ids, global_reservation_ids)
        query = bindings.QueryType(operation, filter_)

        # create payload
        body_payload   = helper.export(query, 'query')
        payload = minisoap.createSoapPayload(body_payload, header_payload)

        def gotReply(data):
            pass

        d = httpclient.soapRequest(provider_nsa.endpoint, actions.QUERY, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(gotReply, self._handleErrorReply)
        return d

