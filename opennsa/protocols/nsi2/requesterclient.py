"""
Web Service protocol for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from dateutil.tz import tzutc

from zope.interface import implements

from twisted.python import log, failure
from twisted.web.error import Error as WebError
from twisted.internet.error import ConnectionRefusedError

from opennsa.interface import INSIProvider
from opennsa import nsa, error
from opennsa.protocols.shared import minisoap, httpclient
from opennsa.protocols.nsi2 import helper
from opennsa.protocols.nsi2.bindings import actions, nsiconnection, p2pservices


LOG_SYSTEM  = 'nsi2.RequesterClient'



class RequesterClient:

    implements(INSIProvider)

    def __init__(self, service_url, reply_to, ctx_factory=None, authz_header=None):

        assert type(service_url) in (str,bytes), 'Service URL must be of type string or bytes'
        self.service_url = service_url
        self.reply_to    = reply_to
        self.ctx_factory = ctx_factory
        self.http_headers = {}
        if authz_header:
            self.http_headers['Authorization'] = authz_header


    def _checkHeader(self, header):

        if header.reply_to and header.correlation_id is None:
            raise AssertionError('Header must specify correlation id, if reply to is specified')


    def _createGenericRequestType(self, body_element_name, header, connection_id):

        header_element = helper.createHeader(header.requester_nsa, header.provider_nsa, self.reply_to, header.correlation_id,
                                             header.session_security_attrs, header.connection_trace)

        body_element = nsiconnection.GenericRequestType(connection_id).xml(body_element_name)

        payload = minisoap.createSoapPayload(body_element, header_element)
        return payload



    def _handleErrorReply(self, err, header):

        if err.check(WebError) is None:
            if err.check(ConnectionRefusedError):
                # could not contact NSA
                msg = 'Could not contact NSA %s. Reason: %s' % (header.provider_nsa, err.getErrorMessage())
                ex = error.DownstreamNSAError(msg, nsa_id=header.provider_nsa)
                return failure.Failure(ex)
            else:
                # cannot handle it here
                return err

        if err.value.status != '500':
            log.msg("Got error with non-500 status. Message: %s" % err.getErrorMessage(), system=LOG_SYSTEM)
            return err

        fault_code, fault_string, detail = minisoap.parseFault(err.value.response)

        service_exception = None
        if detail:
            service_exception = nsiconnection.parse(detail)

        if service_exception is None:
            # this is not entirely correct, but it isn't really wrong either
            ex = error.InternalServerError(fault_string)
        else:
            ex = helper.createException(service_exception, header.provider_nsa)

        err = failure.Failure(ex)

        return err


    def reserve(self, header, connection_id, global_reservation_id, description, criteria):

        self._checkHeader(header)

        # payload construction

        header_element = helper.createHeader(header.requester_nsa, header.provider_nsa, reply_to=self.reply_to, correlation_id=header.correlation_id,
                                             session_security_attributes=header.session_security_attrs, connection_trace=header.connection_trace)

        schedule = criteria.schedule
        sd = criteria.service_def

        assert schedule.start_time.tzinfo is None, 'Start time must NOT have time zone'
        assert schedule.end_time.tzinfo   is None, 'End time must NOT have time zone'

        if not type(sd) is nsa.Point2PointService:
            raise ValueError('Cannot create request for service definition of type %s' % str(type(sd)))

        src_stp_id = helper.createSTPID(sd.source_stp)
        dst_stp_id = helper.createSTPID(sd.dest_stp)

        params = [ p2pservices.TypeValueType(p[0], p[1]) for p in sd.parameters ] if sd.parameters else None
        service_def = p2pservices.P2PServiceBaseType(sd.capacity, sd.directionality, sd.symmetric, src_stp_id, dst_stp_id, sd.ero, params)

        schedule_type = nsiconnection.ScheduleType(schedule.start_time.replace(tzinfo=tzutc()).isoformat(),
                                                   schedule.end_time.replace(tzinfo=tzutc()).isoformat())

        #service_type = str(p2pservices.p2ps)
        service_type = 'http://services.ogf.org/nsi/2013/12/descriptions/EVTS.A-GOLE'
        criteria = nsiconnection.ReservationRequestCriteriaType(criteria.revision, schedule_type, service_type, service_def)

        reservation = nsiconnection.ReserveType(connection_id, global_reservation_id, description, criteria)

        body_payload = reservation.xml(nsiconnection.reserve)
        payload = minisoap.createSoapPayload(body_payload, header_element)

        def _handleAck(soap_data):
            header, ack = helper.parseRequest(soap_data)
            return ack.connectionId

        d = httpclient.soapRequest(self.service_url, actions.RESERVE, payload, ctx_factory=self.ctx_factory, headers=self.http_headers)
        d.addCallbacks(_handleAck, self._handleErrorReply, errbackArgs=(header,))
        return d


    def reserveCommit(self, header, connection_id):

        self._checkHeader(header)

        payload = self._createGenericRequestType(nsiconnection.reserveCommit, header, connection_id)

        d = httpclient.soapRequest(self.service_url, actions.RESERVE_COMMIT, payload, ctx_factory=self.ctx_factory, headers=self.http_headers)
        d.addCallbacks(lambda sd : None, self._handleErrorReply, errbackArgs=(header,))
        return d


    def reserveAbort(self, header, connection_id):

        self._checkHeader(header)

        payload = self._createGenericRequestType(nsiconnection.reserveAbort, header, connection_id)

        d = httpclient.soapRequest(self.service_url, actions.RESERVE_ABORT, payload, ctx_factory=self.ctx_factory, headers=self.http_headers)
        d.addCallbacks(lambda sd : None, self._handleErrorReply, errbackArgs=(header,))

        return d


    def provision(self, header, connection_id):

        self._checkHeader(header)

        payload = self._createGenericRequestType(nsiconnection.provision, header, connection_id)
        d = httpclient.soapRequest(self.service_url, actions.PROVISION, payload, ctx_factory=self.ctx_factory, headers=self.http_headers)
        d.addCallbacks(lambda sd : None, self._handleErrorReply, errbackArgs=(header,))

        return d


    def release(self, header, connection_id):

        self._checkHeader(header)

        payload = self._createGenericRequestType(nsiconnection.release, header, connection_id)
        d = httpclient.soapRequest(self.service_url, actions.RELEASE, payload, ctx_factory=self.ctx_factory, headers=self.http_headers)
        d.addCallbacks(lambda sd : None, self._handleErrorReply, errbackArgs=(header,))
        return d


    def terminate(self, header, connection_id):

        self._checkHeader(header)

        payload = self._createGenericRequestType(nsiconnection.terminate, header, connection_id)
        d = httpclient.soapRequest(self.service_url, actions.TERMINATE, payload, ctx_factory=self.ctx_factory, headers=self.http_headers)
        d.addCallbacks(lambda sd : None, self._handleErrorReply, errbackArgs=(header,))
        return d


    def querySummary(self, header, connection_ids=None, global_reservation_ids=None):

        self._checkHeader(header)

        header_element = helper.createHeader(header.requester_nsa, header.provider_nsa, reply_to=self.reply_to, correlation_id=header.correlation_id,
                                             session_security_attributes=header.session_security_attrs, connection_trace=header.connection_trace)

        query_type = nsiconnection.QueryType(connection_ids, global_reservation_ids)
        body_element = query_type.xml(nsiconnection.querySummary)

        payload = minisoap.createSoapPayload(body_element, header_element)

        d = httpclient.soapRequest(self.service_url, actions.QUERY_SUMMARY, payload, ctx_factory=self.ctx_factory, headers=self.http_headers)
        d.addCallbacks(lambda sd : None, self._handleErrorReply, errbackArgs=(header,))
        return d


    def querySummarySync(self, header, connection_ids=None, global_reservation_ids=None):

        def gotReply(soap_data):
            header, query_confirmed = helper.parseRequest(soap_data)
            return [ helper.buildQuerySummaryResult(resv) for resv in query_confirmed.reservations ]

        # don't need to check header here
        header_element = helper.createHeader(header.requester_nsa, header.provider_nsa, reply_to=self.reply_to, correlation_id=header.correlation_id,
                                             session_security_attributes=header.session_security_attrs, connection_trace=header.connection_trace)

        query_type = nsiconnection.QueryType(connection_ids, global_reservation_ids)
        body_element = query_type.xml(nsiconnection.querySummarySync)

        payload = minisoap.createSoapPayload(body_element, header_element)

        d = httpclient.soapRequest(self.service_url, actions.QUERY_SUMMARY_SYNC, payload, ctx_factory=self.ctx_factory, headers=self.http_headers)
        d.addCallbacks(gotReply, self._handleErrorReply, errbackArgs=(header,))
        return d


