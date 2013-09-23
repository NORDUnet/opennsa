"""
Web Service protocol for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from dateutil.tz import tzutc

from zope.interface import implements

from twisted.python import log, failure
from twisted.web.error import Error as WebError

from opennsa.interface import INSIProvider
from opennsa import nsa, error
from opennsa.protocols.shared import minisoap, httpclient
from opennsa.protocols.nsi2 import helper
from opennsa.protocols.nsi2.bindings import actions, nsiframework, nsiconnection, p2pservices


URN_NETWORK = 'urn:ogf:network:'
LOG_SYSTEM  = 'nsi2.RequesterClient'



class RequesterClient:

    implements(INSIProvider)

    def __init__(self, service_url, reply_to, ctx_factory=None):

        assert type(service_url) in (str,bytes), 'Service URL must be of type string or bytes'
        self.service_url = service_url
        self.reply_to    = reply_to
        self.ctx_factory = ctx_factory


    def _checkHeader(self, header):

        if header.reply_to and header.correlation_id is None:
            raise AssertionError('Header must specify correlation id, if reply to is specified')


    def _createGenericRequestType(self, body_element_name, header, connection_id):

        header_element = helper.createHeader(header.requester_nsa, header.provider_nsa, reply_to=self.reply_to, correlation_id=header.correlation_id)
        body_element = nsiconnection.GenericRequestType(connection_id).xml(body_element_name)

        payload = minisoap.createSoapPayload(body_element, header_element)
        return payload



    def _handleErrorReply(self, err):

        # is this isn't a web error we cannot do anything about it here
        if err.check(WebError) is None:
            return err

        if err.value.status != '500':
            log.msg("Got error with non-500 status. Message: %s" % err.getErrorMessage(), system=LOG_SYSTEM)
            return err

        fault_code, fault_string, detail = minisoap.parseFault(err.value.response)

        service_exception = None
        if detail:
            service_exception = nsiframework.parse(detail)

        if service_exception is None:
            # this is not entirely correct, but it isn't really wrong either
            ex = error.InternalServerError(fault_string)
        else:
            ext = error.lookup(service_exception.errorId)
            ex = ext(service_exception.text)

        err = failure.Failure(ex)

        return err


    def reserve(self, header, connection_id, global_reservation_id, description, criteria):

        self._checkHeader(header)

        # payload construction

        header_payload = helper.createHeader(header.requester_nsa, header.provider_nsa, reply_to=self.reply_to, correlation_id=header.correlation_id)

        schedule = criteria.schedule
        sd = criteria.service_def

        assert schedule.start_time.tzinfo is None, 'Start time must NOT have time zone'
        assert schedule.end_time.tzinfo   is None, 'End time must NOT have time zone'

        if type(sd) is nsa.EthernetVLANService:

            # we pass labels on STPs internally, but not in EVTS service, the latter will change after r99
            src_vlan = sd.source_stp.labels[0].labelValue()
            dst_vlan = sd.dest_stp.labels[0].labelValue()

            src_stp = helper.createSTPType(sd.source_stp)
            dst_stp = helper.createSTPType(sd.dest_stp)
            src_stp.labels = []
            dst_stp.labels = []

            service_type = p2pservices.EthernetVlanType(src_stp, dst_stp, src_vlan, dst_vlan,
                                                        sd.mtu, sd.burst_size, sd.capacity, sd.directionality, sd.symmetric, sd.ero)

        else:
            raise ValueError('Cannot create request for service definition of type %s' % type(service_definition))


        schedule_type = nsiconnection.ScheduleType(schedule.start_time.replace(tzinfo=tzutc()).isoformat(),
                                                   schedule.end_time.replace(tzinfo=tzutc()).isoformat())

        version = 0 # FIXME
        criteria = nsiconnection.ReservationRequestCriteriaType(version, schedule_type, str(p2pservices.evts), { p2pservices.evts : service_type } )

        reservation = nsiconnection.ReserveType(connection_id, global_reservation_id, description, criteria)

        body_payload   = reservation.xml(nsiconnection.reserve)
        payload = minisoap.createSoapPayload(body_payload, header_payload)

        def _handleAck(soap_data):
            header, ack = helper.parseRequest(soap_data)
            return ack.connectionId

        d = httpclient.soapRequest(self.service_url, actions.RESERVE, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(_handleAck, self._handleErrorReply)
        return d


    def reserveCommit(self, header, connection_id):

        self._checkHeader(header)

        payload = self._createGenericRequestType(nsiconnection.reserveCommit, header, connection_id)

        d = httpclient.soapRequest(self.service_url, actions.RESERVE_COMMIT, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(lambda sd : None, self._handleErrorReply)
        return d


    def reserveAbort(self, header, connection_id):

        self._checkHeader(header)

        payload = self._createGenericRequestType(nsiconnection.reserveAbort, header, connection_id)

        d = httpclient.soapRequest(self.service_url, actions.RESERVE_ABORT, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(lambda sd : None, self._handleErrorReply)
        return d


    def provision(self, header, connection_id):

        self._checkHeader(header)

        payload = self._createGenericRequestType(nsiconnection.provision, header, connection_id)
        d = httpclient.soapRequest(self.service_url, actions.PROVISION, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(lambda sd : None, self._handleErrorReply)
        return d


    def release(self, header, connection_id):

        self._checkHeader(header)

        payload = self._createGenericRequestType(nsiconnection.release, header, connection_id)
        d = httpclient.soapRequest(self.service_url, actions.RELEASE, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(lambda sd : None, self._handleErrorReply)
        return d


    def terminate(self, header, connection_id):

        self._checkHeader(header)

        payload = self._createGenericRequestType(nsiconnection.terminate, header, connection_id)
        d = httpclient.soapRequest(self.service_url, actions.TERMINATE, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(lambda sd : None, self._handleErrorReply)
        return d


    def querySummary(self, header, connection_ids=None, global_reservation_ids=None):

        self._checkHeader(header)

        header_element = helper.createHeader(header.requester_nsa, header.provider_nsa, reply_to=self.reply_to, correlation_id=header.correlation_id)

        query_type = nsiconnection.QueryType(connection_ids, global_reservation_ids)
        body_element = query_type.xml(nsiconnection.querySummary)

        payload = minisoap.createSoapPayload(body_element, header_element)

        d = httpclient.soapRequest(self.service_url, actions.QUERY_SUMMARY, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(lambda sd : None, self._handleErrorReply)
        return d


    def querySummarySync(self, header, connection_ids=None, global_reservation_ids=None):

        def gotReply(soap_data):
            header, query_confirmed = helper.parseRequest(soap_data)
            reservations = helper.buildQuerySummaryResult(query_confirmed)
            return reservations

        # don't need to check header here

        header_element = helper.createHeader(header.requester_nsa, header.provider_nsa, reply_to=self.reply_to, correlation_id=header.correlation_id)

        query_type = nsiconnection.QueryType(connection_ids, global_reservation_ids)
        body_element = query_type.xml(nsiconnection.querySummary)

        payload = minisoap.createSoapPayload(body_element, header_element)

        d = httpclient.soapRequest(self.service_url, actions.QUERY_SUMMARY_SYNC, payload, ctx_factory=self.ctx_factory)
        d.addCallbacks(gotReply, self._handleErrorReply)
        return d


