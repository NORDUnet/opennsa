"""
Web Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from twisted.python import log
from twisted.web import resource, server

from opennsa import nsa
from opennsa.protocols.webservice.ext import sudsservice


WSDL_PROVIDER   = 'file:///home/htj/nsi/opennsa/wsdl/ogf_nsi_connection_provider_v1_0.wsdl'
WSDL_REQUESTER  = 'file:///home/htj/nsi/opennsa/wsdl/ogf_nsi_connection_requester_v1_0.wsdl'

# URL for service is http://HOST:PORT/NSI/services/ConnectionService


class ConnectionServiceResource(resource.Resource):

    isLeaf = True

    def __init__(self, nsi_service):
        resource.Resource.__init__(self)
        self.nsi_service = nsi_service

        self.provider_decoder  = sudsservice.WSDLMarshaller(WSDL_PROVIDER)
        self.requester_decoder = sudsservice.WSDLMarshaller(WSDL_REQUESTER)


    def render_POST(self, request):

        soap_action = request.requestHeaders.getRawHeaders('soapaction',[None])[0]

        if self.provider_decoder.recognizedSOAPAction(soap_action):
            decoder = self.provider_decoder
        elif self.requester_decoder.recognizedSOAPAction(soap_action):
            decoder = self.requester_decoder
        else:
            log.msg('Got request with unknown SOAP action: %s' % soap_action, system='opennsa.ConnectionServiceResource')
            request.setResponseCode(406) # Not acceptable
            return 'Invalid SOAP Action for this resource'

        soap_action = soap_action[1:-1] # remove front and end ""

        log.msg('Got request with SOAP action: %s' % soap_action, system='opennsa.ConnectionServiceResource')

        short_soap_action = soap_action.split('/')[-1]
        method, objs = decoder.parse_request(short_soap_action, request.content.getvalue())

        if short_soap_action == 'reservation':
            #correlation_id_tuple, reply_to_tuple, reservation_requesa_tuple = objs
            correlation_id, reply_to, res_req = [ a for (_,a) in objs ]
            #log.msg("Received SOAP request. Correlation ID: %s. Connection ID: %s" % (correlation_id, res_req.reservation.connectionId))
            #print res_req

            requester_nsa           = nsa.NetworkServiceAgent(res_req.requesterNSA)
            provider_nsa            = nsa.NetworkServiceAgent(res_req.providerNSA)
            session_security_attr   = None
            global_reservation_id   = res_req.reservation.globalReservationId
            description             = res_req.reservation.description
            connection_id           = res_req.reservation.connectionId

            sp      = res_req.reservation.serviceParameters
            path    = res_req.reservation.path

            def parseSTPID(std_id):
                tokens = path.sourceSTP.stpId.replace(nsa.STP_PREFIX, '').split(':', 2)
                return nsa.STP(tokens[0], tokens[1])

            source_stp  = parseSTPID(path.sourceSTP.stpId)
            dest_stp    = parseSTPID(path.destSTP.stpId)
            # how to check for existence of optional parameters easily...
            service_parameters      = nsa.ServiceParameters(sp.schedule.startTime, None, source_stp, dest_stp, bandwidth_desired=sp.bandwidth.desired)

            d = self.nsi_service.reserve(requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters, reply_to)
            d.addErrback(lambda err : log.err(err))
            # The deferred will fire when the reservation is made.

            # The initial reservation ACK should be send when the reservation
            # request is persistent, and a callback should then be issued once
            # the connection has been reserved. Unfortuantely there is
            # currently no way of telling when the request is persitent, so we
            # just return immediately.
            reply = decoder.marshal_result(correlation_id, method)


        elif short_soap_action == 'reservationConfirmed':

            res_conf = objs
            rc = res_conf.reservationConfirmed
            res = rc.reservation

            def reply(connection_id):
                reply = decoder.marshal_result(res_conf.correlationId, method)
                request.write(reply)
                request.finish()

            requester_nsa = nsa.NetworkServiceAgent(rc.requesterNSA)
            provider_nsa  = nsa.NetworkServiceAgent(rc.providerNSA)

            d = self.nsi_service.reservationConfirmed(requester_nsa, provider_nsa, str(res.globalReservationId), str(res.description), str(res.connectionId), None)
            d.addCallback(reply)
            return server.NOT_DONE_YET


        elif short_soap_action == 'provision':

            req = objs

            def reply(connection_id):
                reply = decoder.marshal_result(str(req.correlationId), method)
                request.write(reply)
                request.finish()

            requester_nsa = nsa.NetworkServiceAgent(req.provision.requesterNSA)
            provider_nsa  = nsa.NetworkServiceAgent(req.provision.providerNSA)

            d = self.nsi_service.provision(requester_nsa, provider_nsa, None, str(req.provision.connectionId))
            d.addCallback(reply)
            return server.NOT_DONE_YET


        return reply



def createNSIWSService(nsi_service):

    # this may seem a bit much, but makes it much simpler to add or change something later
    top_resource = resource.Resource()
    nsi_resource = resource.Resource()
    services_resource = resource.Resource()

    connection_service = ConnectionServiceResource(nsi_service)

    top_resource.putChild('NSI', nsi_resource)
    nsi_resource.putChild('services', services_resource)
    services_resource.putChild('ConnectionService', connection_service)

    site = server.Site(top_resource)
    return site

