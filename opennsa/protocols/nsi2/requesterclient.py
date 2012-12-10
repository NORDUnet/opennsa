"""
Web Service protocol for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from twisted.python import log

from opennsa.protocols.shared import minisoap

from opennsa.protocols.nsi2 import connectiontypes as CT, headertypes as HT, actions



#URN_UUID_PREFIX = 'urn:uuid:'
FRAMEWORK_TYPES_NS  = "http://schemas.ogf.org/nsi/2012/03/framework/types"
CONNECTION_TYPES_NS = "http://schemas.ogf.org/nsi/2012/03/connection/types"



def utcTime(dt):
    return dt.isoformat().rsplit('.',1)[0] + 'Z'


#def createCorrelationId():
#    return URN_UUID_PREFIX + str(uuid.uuid1())


class RequesterClient:

    def __init__(self, reply_to, ctx_factory=None):

        self.reply_to = reply_to
        self.ctx_factory = ctx_factory


#    def _createGenericRequestType(self, requester_nsa, provider_nsa, connection_id):
#
#        req = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}GenericRequestType')
#        req.requesterNSA = requester_nsa.urn()
#        req.providerNSA  = provider_nsa.urn()
#        req.connectionId = connection_id
#        return req


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

#        f1 = StringIO.StringIO()
#        header.export(f1,0, namespacedef_='xmlns:tns="%s"' % FRAMEWORK_TYPES_NS)
#        header_payload = f1.getvalue()
#
#        f2 = StringIO.StringIO()
#        reservation.export(f2,0, namespacedef_='xmlns:tns="%s"' % CONNECTION_TYPES_NS)
#        body_payload = f2.getvalue()

        header_payload = minisoap.serializeType(header,      'xmlns:tns="%s"' % FRAMEWORK_TYPES_NS)
        body_payload   = minisoap.serializeType(reservation, 'xmlns:tns="%s"' % CONNECTION_TYPES_NS)

        payload = minisoap.createSoapPayload(body_payload, header_payload)

        def gotReply(data):
            log.msg(' -- Received Response Payload --\n' + data + '\n -- END. Received Response Payload --', payload=True)

        #print "--\n", service_url
        f = minisoap.httpRequest(service_url, actions.RESERVE, payload, ctx_factory=self.ctx_factory)
        f.deferred.addCallbacks(gotReply) #, errReply)
        return f.deferred


#        d = self.client.invoke(provider_nsa.url(), 'reserve', correlation_id, self.reply_to, res_req)
#        return d


    def provision(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id):

        req = self._createGenericRequestType(requester_nsa, provider_nsa, connection_id)
        d = self.client.invoke(provider_nsa.url(), 'provision', correlation_id, self.reply_to, req)
        return d


    def release(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id):

        req = self._createGenericRequestType(requester_nsa, provider_nsa, connection_id)
        d = self.client.invoke(provider_nsa.url(), 'release', correlation_id, self.reply_to, req)
        return d


    def terminate(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id):

        req = self._createGenericRequestType(requester_nsa, provider_nsa, connection_id)
        d = self.client.invoke(provider_nsa.url(), 'terminate', correlation_id, self.reply_to, req)
        return d


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


