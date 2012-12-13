"""
Web Service protocol for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from twisted.python import log
from twisted.web.error import Error as WebError

from opennsa.protocols.shared import minisoap

from opennsa.protocols.nsi2 import connectiontypes as CT, headertypes as HT, actions, helper




def utcTime(dt):
    return dt.isoformat().rsplit('.',1)[0] + 'Z'



class RequesterClient:

    def __init__(self, reply_to, ctx_factory=None):

        self.reply_to = reply_to
        self.ctx_factory = ctx_factory


    def _createGenericRequestType(self, correlation_id, requester_nsa, provider_nsa, connection_id):

        # this could be more compact
        header = HT.CommonHeaderType(None, correlation_id, requester_nsa.urn(), provider_nsa.urn(), self.reply_to)

        request = CT.GenericRequestType(connection_id)

        header_payload = helper.export(header,  helper.FRAMEWORK_TYPES_NS)
        body_payload   = helper.export(request, helper.CONNECTION_TYPES_NS)

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

        from xml.etree import cElementTree as ET

        fault_tree = ET.fromstring(payload)

        print "FT", fault_tree

        body = fault_tree.getchildren()[0]
        print "BD", body
        fault = body.getchildren()[0]
        print "FT", fault

        # extract faultString and errorId

        return err


    def reserve(self, service_url, correlation_id, requester_nsa, provider_nsa, session_security_attr,
                global_reservation_id, description, connection_id, service_parameters):

        header = HT.CommonHeaderType(None, correlation_id, requester_nsa.urn(), provider_nsa.urn(), self.reply_to)

        sp = service_parameters
        s_stp = sp.source_stp
        d_stp = sp.dest_stp

        schedule = CT.ScheduleType(sp.start_time, sp.end_time)
        service_attributes = None

        # EROs not supported, need to use TypeValuePairListType for labels
        source_stp = CT.StpType(s_stp.network, s_stp.endpoint, None, 'Ingress')
        dest_stp   = CT.StpType(d_stp.network, d_stp.endpoint, None, 'Egress')
        path = CT.PathType(sp.directionality, None, source_stp, dest_stp)

        criteria = CT.ReservationRequestCriteriaType(schedule, sp.bandwidth, service_attributes, path)

        reservation = CT.ReserveType(global_reservation_id, description, connection_id, criteria)

        # create payloads

        header_payload = helper.export(header,      helper.FRAMEWORK_TYPES_NS)
        body_payload   = helper.export(reservation, helper.CONNECTION_TYPES_NS)

        payload = minisoap.createSoapPayload(body_payload, header_payload)

        def gotReply(data):
            log.msg(' -- Received Response Payload --\n' + data + '\n -- END. Received Response Payload --', payload=True)

        #print "--\n", service_url
        f = minisoap.httpRequest(provider_nsa.url(), actions.RESERVE, payload, ctx_factory=self.ctx_factory)
        f.deferred.addCallbacks(gotReply, self._handleErrorReply)
        return f.deferred


    def provision(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id):

        payload = self._createGenericRequestType(correlation_id, requester_nsa, provider_nsa, connection_id)

        def gotReply(data):
            log.msg(' -- START: Provision Response --\n' + data + '\n -- END. Provision Response --', payload=True)

        f = minisoap.httpRequest(provider_nsa.url(), actions.PROVISION, payload, ctx_factory=self.ctx_factory)
        f.deferred.addCallbacks(gotReply) #, errReply)
        return f.deferred


    def release(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id):

        def gotReply(data):
            log.msg(' -- START: Release Response --\n' + data + '\n -- END. Release Response --', payload=True)

        payload = self._createGenericRequestType(correlation_id, requester_nsa, provider_nsa, connection_id)
        f = minisoap.httpRequest(provider_nsa.url(), actions.RELEASE, payload, ctx_factory=self.ctx_factory)
        f.deferred.addCallbacks(gotReply) #, errReply)
        return f.deferred


    def terminate(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id):

        def gotReply(data):
            log.msg(' -- START: Terminate Response --\n' + data + '\n -- END. Terminate Response --', payload=True)

        payload = self._createGenericRequestType(correlation_id, requester_nsa, provider_nsa, connection_id)
        f = minisoap.httpRequest(provider_nsa.url(), actions.TERMINATE, payload, ctx_factory=self.ctx_factory)
        f.deferred.addCallbacks(gotReply) #, errReply)
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


