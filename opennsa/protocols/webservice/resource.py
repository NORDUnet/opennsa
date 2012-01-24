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

        # log peer identity if using ssl/tls at some point we should probably do something with the identity
        if request.isSecure():
            cert = request.transport.getPeerCertificate()
            if cert:
                subject = '/' + '/'.join([ '='.join(c) for c in cert.get_subject().get_components() ])
                log.msg('Certificate subject: %s' % subject, system='opennsa.SOAPResource')

        soap_action = request.requestHeaders.getRawHeaders('soapaction',[None])[0]

        if not soap_action in self.soap_actions:
            log.msg('Got request with unknown SOAP action: %s' % soap_action, system='opennsa.SOAPResource')
            request.setResponseCode(406) # Not acceptable
            return 'Invalid SOAP Action for this resource'

        decoder = self.soap_actions[soap_action]
        soap_data = request.content.read()

        log.msg('Received SOAP request. Action: %s. Length: %i' % (soap_action, len(soap_data)), system='opennsa.ConnectionServiceResource', debug=True)

        def reply(reply_data):
            if reply_data is None or len(reply_data) == 0:
                log.msg('None/empty reply data supplied for SOAPResource. This is probably wrong', system='opennsa.SOAPResource')
            request.setHeader('Content-Type', 'text/xml') # Keeps some SOAP implementations happy
            request.write(reply_data)
            request.finish()

        def decodeError(err):
            error_msg = err.getErrorMessage()
            log.msg('Failure during SOAP decoding/dispatch: %s' % error_msg)
            log.err(err)
            request.setResponseCode(500) # Internal server error
            request.setHeader('Content-Type', 'text/plain') # This will make some SOAP implementation sad, but there isn't alot that can be done at this point
            request.write(error_msg)
            request.finish()

        d = defer.maybeDeferred(decoder, soap_action, soap_data)
        d.addCallbacks(reply, decodeError)

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

    site = server.Site(top_resource, logPath='/dev/null')
    return soap_resource, site

