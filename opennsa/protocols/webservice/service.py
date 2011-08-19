"""
Web Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from twisted.python import log

from opennsa import nsa
from opennsa.protocols.webservice.ext import sudsservice


WSDL_PROVIDER   = 'file:///home/htj/nsi/opennsa/wsdl/ogf_nsi_connection_provider_v1_0.wsdl'
WSDL_REQUESTER  = 'file:///home/htj/nsi/opennsa/wsdl/ogf_nsi_connection_requester_v1_0.wsdl'



def _decodeNSAs(subreq):
    requester_nsa = nsa.NetworkServiceAgent(str(subreq.requesterNSA))
    provider_nsa  = nsa.NetworkServiceAgent(str(subreq.providerNSA))
    return requester_nsa, provider_nsa



class ProviderService:

    def __init__(self, soap_resource, provider):

        self.provider = provider
        self.soap_resource = soap_resource
        #self.nsi_service = nsi_service
        self.decoder = sudsservice.WSDLMarshaller(WSDL_PROVIDER)

        # not sure what query callbacs are doing here
        #self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/07/connection/service/queryConfirmed"', ...)
        #self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/07/connection/service/queryFailed"', ...)
        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/07/connection/service/reservation"',   self.reservation)
        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/07/connection/service/provision"',     self.provision)
        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/07/connection/service/release"',       self.release)
        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/07/connection/service/terminate"',     self.terminate)
        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/07/connection/service/query"',         self.query)


    def genericReply(connection_id, request, decoder, method, correlation_id):
        reply = decoder.marshal_result(correlation_id, method)
        return reply


    def reservation(self, soap_action, soap_data):

        assert soap_action == '"http://schemas.ogf.org/nsi/2011/07/connection/service/reservation"'
        method, objs = self.decoder.parse_request('reservation', soap_data)

        correlation_id, reply_to, req = [ a for (_,a) in objs ]
        #log.msg("Received SOAP request. Correlation ID: %s. Connection ID: %s" % (correlation_id, req.reservation.connectionId))
        #print req

        reply_to = str(reply_to)

        requester_nsa, provider_nsa = _decodeNSAs(req)
        session_security_attr       = None
        global_reservation_id       = req.reservation.globalReservationId
        description                 = req.reservation.description
        connection_id               = req.reservation.connectionId
        sp                          = req.reservation.serviceParameters
        path                        = req.reservation.path

        def parseSTPID(std_id):
            tokens = path.sourceSTP.stpId.replace(nsa.STP_PREFIX, '').split(':', 2)
            return nsa.STP(tokens[0], tokens[1])

        source_stp  = parseSTPID(path.sourceSTP.stpId)
        dest_stp    = parseSTPID(path.destSTP.stpId)
        # how to check for existence of optional parameters easily  - in / hasattr both works
        service_parameters      = nsa.ServiceParameters(sp.schedule.startTime, None, source_stp, dest_stp, bandwidth_desired=sp.bandwidth.desired)

        d = self.provider.reservation(correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters)
        #d = self.nsi_service.reserve(requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters, reply_to)
        d.addErrback(lambda err : log.err(err))
        # The deferred will fire when the reservation is made.

        # The initial reservation ACK should be send when the reservation
        # request is persistent, and a callback should then be issued once
        # the connection has been reserved. Unfortuantely there is
        # currently no way of telling when the request is persitent, so we
        # just return immediately.
        reply = self.decoder.marshal_result(correlation_id, method)
        return reply


    def provision(self, soap_action, soap_data):

        method, req = self.decoder.parse_request('provision', soap_data)
        requester_nsa, provider_nsa = _decodeNSAs(req.provision)

        correlation_id  = str(req.correlationId)
        reply_to        = str(req.replyTo)

        connection_id   = str(req.provision.connectionId)

        d = self.provider.provision(correlation_id, reply_to, requester_nsa, provider_nsa, None, connection_id)

        reply = self.decoder.marshal_result(correlation_id, method)
        return reply


    def release(self, soap_action, soap_data):

        method, req = self.decoder.parse_request('release', soap_data)
        requester_nsa, provider_nsa = _decodeNSAs(req.release)

        correlation_id  = str(req.correlationId)
        reply_to        = str(req.replyTo)
        connection_id   = str(req.release.connectionId)

        d = self.provider.release(correlation_id, reply_to, requester_nsa, provider_nsa, None, connection_id)

        reply = self.decoder.marshal_result(correlation_id, method)
        return reply



    def terminate(self, soap_action, soap_data):

        method, req = self.decoder.parse_request('terminate', soap_data)
        requester_nsa, provider_nsa = _decodeNSAs(req.terminate)

        correlation_id  = str(req.correlationId)
        reply_to        = str(req.replyTo)
        connection_id   = str(req.terminate.connectionId)

        d = self.provider.terminate(correlation_id, reply_to, requester_nsa, provider_nsa, None, connection_id)

        reply = self.decoder.marshal_result(correlation_id, method)
        return reply


    def query(self, soap_action, soap_data):
        print "QUERY"
        method, req = self.decoder.parse_request('query', soap_data)
        raise NotImplementedError('query')

        #print "Q", req
        requester_nsa, provider_nsa = _decodeNSAs(req.query)

        operation = req.query.operation
        qf = req.query.queryFilter

        connection_ids = []
        global_reservation_ids = []

        if 'connectionId' in qf:
            connection_ids = qf.connectionId
        if 'globalReservationId' in qf:
            global_reservation_ids = qf.globalReservationId

        #print "QQ", operation, connection_ids, global_reservation_ids

        def queryReply(query_result):

            res = self.decoder.createType('{http://schemas.ogf.org/nsi/2011/07/connection/types}QueryConfirmedType')
            #print "QRES", res
            reply = self.decoder.marshal_result(str(req.correlationId), method)
            return reply

        d = self.nsi_service.query(requester_nsa, provider_nsa, None, operation, connection_ids, global_reservation_ids)
        d.addCallback(queryReply)
        return d



class RequesterService:

    def __init__(self, soap_resource, requester):

        self.soap_resource = soap_resource
        self.requester = requester
        self.decoder = sudsservice.WSDLMarshaller(WSDL_REQUESTER)

        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/07/connection/service/reservationConfirmed"',  self.reservationConfirmed)
        self.soap_resource.registerDecoder("http://schemas.ogf.org/nsi/2011/07/connection/service/reservationFailed",       self.reservationFailed)

        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/07/connection/service/provisionConfirmed"',    self.provisionConfirmed)
        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/07/connection/service/provisionFailed"',       self.provisionFailed)

        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/07/connection/service/releaseConfirmed"',      self.releaseConfirmed)
        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/07/connection/service/releaseFailed"',         self.releaseFailed)

        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/07/connection/service/terminateConfirmed"',    self.terminateConfirmed)
        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/07/connection/service/terminateFailed"',       self.terminateFailed)

#"http://schemas.ogf.org/nsi/2011/07/connection/service/queryConfirmed"
#"http://schemas.ogf.org/nsi/2011/07/connection/service/forcedEnd"
#"http://schemas.ogf.org/nsi/2011/07/connection/service/queryFailed"

#"http://schemas.ogf.org/nsi/2011/07/connection/service/query"


    def reservationConfirmed(self, soap_action, soap_data):

        assert soap_action == '"http://schemas.ogf.org/nsi/2011/07/connection/service/reservationConfirmed"'

        method, req = self.decoder.parse_request('reservationConfirmed', soap_data)
        requester_nsa, provider_nsa = _decodeNSAs(req.reservationConfirmed)
        res = req.reservationConfirmed.reservation

        correlation_id          = str(req.correlationId)
        global_reservation_id   = str(res.globalReservationId)
        description             = str(res.description)
        connection_id           = str(res.connectionId)

        self.requester.reservationConfirmed(correlation_id, requester_nsa, provider_nsa, None, global_reservation_id, description, connection_id, None)

        reply = self.decoder.marshal_result(correlation_id, method)
        return reply


    def reservationFailed(self, soap_action, soap_data):
        print "RES FAILE :-("


    def provisionConfirmed(self, soap_action, soap_data):

        assert soap_action == '"http://schemas.ogf.org/nsi/2011/07/connection/service/provisionConfirmed"'

        method, req = self.decoder.parse_request('provisionConfirmed', soap_data)
        requester_nsa, provider_nsa = _decodeNSAs(req.provisionConfirmed)

        correlation_id          = str(req.correlationId)
        connection_id           = str(req.provisionConfirmed.connectionId)

        d = self.requester.provisionConfirmed(correlation_id, requester_nsa, provider_nsa, None, connection_id)

        reply = self.decoder.marshal_result(correlation_id, method)
        return reply


    def provisionFailed(self, soap_action, soap_data):

        assert soap_action == '"http://schemas.ogf.org/nsi/2011/07/connection/service/provisionFailed"'
        method, req = self.decoder.parse_request('provisionFailed', soap_data)

        requester_nsa, provider_nsa = _decodeNSAs(req.provisionFailed)
        d = self.nsi_service.provisionFailed(requester_nsa, provider_nsa, None, str(req.provisionFailed.connectionId))

        return ''


    def releaseConfirmed(self, soap_action, soap_data):

        assert soap_action == '"http://schemas.ogf.org/nsi/2011/07/connection/service/releaseConfirmed"'

        method, req = self.decoder.parse_request('releaseConfirmed', soap_data)
        requester_nsa, provider_nsa = _decodeNSAs(req.releaseConfirmed)

        correlation_id          = str(req.correlationId)
        connection_id           = str(req.releaseConfirmed.connectionId)

        d = self.requester.releaseConfirmed(correlation_id, requester_nsa, provider_nsa, None, connection_id)

        reply = self.decoder.marshal_result(correlation_id, method)
        return reply


    def releaseFailed(self, soap_action, soap_data):
        print "SERVICE RELEASE FAILED"


    def terminateConfirmed(self, soap_action, soap_data):

        assert soap_action == '"http://schemas.ogf.org/nsi/2011/07/connection/service/terminateConfirmed"'

        method, req = self.decoder.parse_request('terminateConfirmed', soap_data)
        requester_nsa, provider_nsa = _decodeNSAs(req.terminateConfirmed)

        correlation_id          = str(req.correlationId)
        connection_id           = str(req.terminateConfirmed.connectionId)

        d = self.requester.terminateConfirmed(correlation_id, requester_nsa, provider_nsa, None, connection_id)

        reply = self.decoder.marshal_result(correlation_id, method)
        return reply


    def terminateFailed(self, soap_action, soap_data):
        print "SERVICE TERMINATE FAILED"


