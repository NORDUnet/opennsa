"""
Web Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from twisted.python import log
from twisted.internet import defer
from twisted.web import resource, server


# URL for service is http://HOST:PORT/NSI/services/ConnectionService


class SOAPResource(resource.Resource):

    isLeaf = True

    def __init__(self):
        resource.Resource.__init__(self)
        self.soap_actions = {}


    def registerDecoder(self, soap_action, decoder):

        self.soap_actions[soap_action] = decoder


    def render_POST(self, request):

        soap_action = request.requestHeaders.getRawHeaders('soapaction',[None])[0]

        if not soap_action in self.soap_actions:
            log.msg('Got request with unknown SOAP action: %s' % soap_action, system='opennsa.SOAPResource')
            request.setResponseCode(406) # Not acceptable
            return 'Invalid SOAP Action for this resource'

        log.msg('Got request with SOAP action: %s' % soap_action, system='opennsa.ConnectionServiceResource')

        decoder = self.soap_actions[soap_action]
        soap_data = request.content.getvalue()

        def reply(reply_data):
            if reply_data is None or len(reply_data) == 0:
                log.msg('None/empty reply data supplied for SOAPResource. This is probably wrong')
            request.write(reply_data)
            request.finish()

        d = defer.maybeDeferred(decoder, soap_action, soap_data)
        d.addCallback(reply)

        return server.NOT_DONE_YET



def createService():

    # this may seem a bit much, but makes it much simpler to add or change something later
    top_resource = resource.Resource()
    nsi_resource = resource.Resource()
    services_resource = resource.Resource()

    soap_resource = SOAPResource()

    top_resource.putChild('NSI', nsi_resource)
    nsi_resource.putChild('services', services_resource)
    services_resource.putChild('ConnectionService', soap_resource)

    site = server.Site(top_resource)
    return soap_resource, site

