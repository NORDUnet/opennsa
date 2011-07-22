"""
Web Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from twisted.python import log
from twisted.web import resource, server

from opennsa.protocol.webservice import soap as nsisoap


# URL for service is http://HOST:PORT/NSI/services/ConnectionService


class ConnectionServiceResource(resource.Resource):

    isLeaf = True

    def __init__(self, nsi_service):
        resource.Resource.__init__(self)
        self.decoder = nsisoap.NSIWSDecoder()

    def render_POST(self, request):

        soap_action = request.requestHeaders.getRawHeaders('soapaction',[None])[0]
        if not soap_action in nsisoap.ACCEPTED_SOAP_ACTIONS:
            request.setResponseCode(406) # Not acceptable
            return 'Invalid SOAP Action for this resource'

        log.msg('Got request with SOAP action: %s' % soap_action, system='opennsa.ConnectionServiceResource')

        #transaction_id, reply_to, request = self.decoder.decodeRequest(soap_action, request.content)
        args = self.decoder.decodeRequest(soap_action, request.content)

        #print "T", transaction_id, reply_to #, request

        # reply = self.decoder.encodeRequest()
        # print reply


        return nsisoap.GENERIC_RESPONSE_TYPE



def createNSIWSResourceTree(nsi_service):

    # this may seem a bit much, but makes it much simpler to add or change something later
    top_resource = resource.Resource()
    nsi_resource = resource.Resource()
    services_resource = resource.Resource()

    connection_service = ConnectionServiceResource(nsi_service)

    top_resource.putChild('NSI', nsi_resource)
    nsi_resource.putChild('services', services_resource)
    services_resource.putChild('ConnectionService', connection_service)

    return top_resource


# resource = createNSIWSResourceTree(None)
# site = server.Site(resource)
# application = service.Application("OpenNSA-WS-Test")
# internet.TCPServer(9080, site, interface='localhost').setServiceParent(application)

