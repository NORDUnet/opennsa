"""
Web Service protocol for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from zope.interface import implements

from twisted.python import log, failure
from twisted.web.error import Error as WebError

from opennsa.interface import INSIProvider
from opennsa import error
from opennsa.protocols.shared import minisoap, httpclient
from opennsa.protocols.nsi2 import actions, bindings, helper


URN_NETWORK = 'urn:ogf:network:'


def utcTime(dt):
    return dt.isoformat().rsplit('.',1)[0] + 'Z'



class RequesterClient:

    implements(INSIProvider)

    def __init__(self, providers, reply_to, ctx_factory=None):

        self.providers   = providers
        self.reply_to    = reply_to
        self.ctx_factory = ctx_factory


    def _checkHeader(self, header):

        if header.reply_to and header.correlation_id is None:
            raise ValueError('Header must specify correlation id, if reply to is specified')


    def _createGenericRequestType(self, body_element_name, header, connection_id):

        header_element = helper.createHeader(header.requester_nsa, header.provider_nsa, reply_to=self.reply_to, correlation_id=header.correlation_id)
        body_element = bindings.GenericRequestType(connection_id).xml(body_element_name)

        payload = minisoap.createSoapPayload(body_element, header_element)
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
            service_exception = bindings.parse(detail)

        if service_exception is None:
            # this is not entirely correct, but it isn't really wrong either
            ex = error.InternalServerError(fault_string)
        else:
            ext = error.lookup(service_exception.errorId)
            ex = ext(service_exception.text)

        err = failure.Failure(ex)

        return err


    def reserve(self, header, connection_id, global_reservation_id, description, service_parameters):

        self._checkHeader(header)

        service_url = self.providers[header.provider_nsa]

        # payload construction

        header_payload = helper.createHeader(header.requester_nsa, header.provider_nsa, reply_to=self.reply_to, correlation_id=header.correlation_id)

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

        criteria = bindings.ReservationRequestCriteriaType(service_parameters.version, schedule, sp.bandwidth, service_attributes, path)

        reservation = bindings.ReserveType(connection_id, global_reservation_id, description, criteria)

        body_payload   = reservation.xml(bindings.reserve)
        payload = minisoap.createSoapPayload(body_payload, header_payload)

        def _handleAck(soap_data):
            header, ack = helper.parseRequest(soap_data)
            return ack.connectionId

        d = httpclient.soapRequest(service_url, actions.RESERVE, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(_handleAck, self._handleErrorReply)
        return d


    def reserveCommit(self, header, connection_id):

        self._checkHeader(header)
        service_url = self.providers[header.provider_nsa]

        payload = self._createGenericRequestType(bindings.reserveCommit, header, connection_id)

        d = httpclient.soapRequest(service_url, actions.RESERVE_COMMIT, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(lambda sd : None, self._handleErrorReply)
        return d


    def reserveAbort(self, header, connection_id):

        self._checkHeader(header)
        service_url = self.providers[header.provider_nsa]

        payload = self._createGenericRequestType(bindings.reserveAbort, header, connection_id)

        d = httpclient.soapRequest(service_url, actions.RESERVE_ABORT, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(lambda sd : None, self._handleErrorReply)
        return d


    def provision(self, header, connection_id):

        self._checkHeader(header)
        service_url = self.providers[header.provider_nsa]

        payload = self._createGenericRequestType(bindings.provision, header, connection_id)
        d = httpclient.soapRequest(service_url, actions.PROVISION, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(lambda sd : None, self._handleErrorReply)
        return d


    def release(self, header, connection_id):

        self._checkHeader(header)
        service_url = self.providers[header.provider_nsa]

        payload = self._createGenericRequestType(bindings.release, header, connection_id)
        d = httpclient.soapRequest(service_url, actions.RELEASE, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(lambda sd : None, self._handleErrorReply)
        return d


    def terminate(self, header, connection_id):

        self._checkHeader(header)
        service_url = self.providers[header.provider_nsa]

        payload = self._createGenericRequestType(bindings.terminate, header, connection_id)
        d = httpclient.soapRequest(service_url, actions.TERMINATE, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(lambda sd : None, self._handleErrorReply)
        return d


    def querySummary(self, header, connection_ids=None, global_reservation_ids=None):

        service_url = self.providers[header.provider_nsa]

        header_element = helper.createHeader(header.requester_nsa, header.provider_nsa, reply_to=self.reply_to, correlation_id=header.correlation_id)

        query_type = bindings.QueryType(connection_ids, global_reservation_ids)
        body_element = query_type.xml(bindings.querySummary)

        payload = minisoap.createSoapPayload(body_element, header_element)

        d = httpclient.soapRequest(service_url, actions.QUERY_SUMMARY, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(lambda sd : None, self._handleErrorReply)
        return d


    def querySummarySync(self, header, connection_ids=None, global_reservation_ids=None):

        def gotReply(soap_data):
            header, query_confirmed = helper.parseRequest(soap_data)
            reservations = helper.buildQuerySummaryResult(query_confirmed)
            return reservations

        # don't need to check header here
        service_url = self.providers[header.provider_nsa]

        header_element = helper.createHeader(header.requester_nsa, header.provider_nsa, reply_to=self.reply_to, correlation_id=header.correlation_id)

        query_type = bindings.QueryType(connection_ids, global_reservation_ids)
        body_element = query_type.xml(bindings.querySummary)

        payload = minisoap.createSoapPayload(body_element, header_element)

        d = httpclient.soapRequest(service_url, actions.QUERY_SUMMARY_SYNC, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(gotReply, self._handleErrorReply)
        return d


