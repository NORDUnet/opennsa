"""
Web Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from twisted.python import log
from twisted.web import resource, server

from opennsa.protocols.webservice.ext import sudsservice


WSDL_PROVIDER   = 'file:///home/htj/nsi/opennsa/wsdl/ogf_nsi_connection_provider_v1_0.wsdl'
WSDL_REQUESTER  = 'file:///home/htj/nsi/opennsa/wsdl/ogf_nsi_connection_requester_v1_0.wsdl'

# URL for service is http://HOST:PORT/NSI/services/ConnectionService


class ConnectionServiceResource(resource.Resource):

    isLeaf = True

    def __init__(self, nsi_service):
        resource.Resource.__init__(self)
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
            correlation_id, reply_to, reservation_request = [ a for (_,a) in objs ]
            print "Received request. Correlation ID: %s. Connection ID: %s" % (correlation_id, reservation_request.reservation.connectionId)
            #self.nsi_service.reserve(requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters)
            reply = decoder.marshal_result(correlation_id, method)

        elif short_soap_action == 'reservationConfirmed':
            corr_id = objs[0]
            reply = decoder.marshal_result(corr_id, method)


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

