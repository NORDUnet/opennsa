"""
Web Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

from twisted.python import log
from twisted.internet import defer
from twisted.web import resource, server


LOG_SYSTEM = 'protocol.SOAPResource'


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
                log.msg('Certificate subject: %s' % subject, system=LOG_SYSTEM)

        soap_action = request.requestHeaders.getRawHeaders('soapaction',[None])[0]

        soap_data = request.content.read()
        log.msg(" -- Received payload --\n%s\n -- End of payload --" % soap_data, system=LOG_SYSTEM, payload=True)

        if not soap_action in self.soap_actions:
            log.msg('Got request with unknown SOAP action: %s' % soap_action, system=LOG_SYSTEM)
            request.setResponseCode(406) # Not acceptable
            return 'Invalid SOAP Action for this resource'

        log.msg('Received SOAP request. Action: %s. Length: %i' % (soap_action, len(soap_data)), system=LOG_SYSTEM, debug=True)

        def reply(reply_data):
            if reply_data is None or len(reply_data) == 0:
                log.msg('None/empty reply data supplied for SOAPResource. This is probably wrong', system=LOG_SYSTEM)
            request.setHeader('Content-Type', 'text/xml') # Keeps some SOAP implementations happy
            request.write(reply_data)
            request.finish()

        def decodeError(err):
            error_msg = err.getErrorMessage()
            log.msg('Failure during SOAP decoding/dispatch: %s' % error_msg, system=LOG_SYSTEM)
            log.err(err)
            request.setResponseCode(500) # Internal server error
            request.setHeader('Content-Type', 'text/plain') # This will make some SOAP implementation sad, but there isn't alot that can be done at this point
            request.write(error_msg)
            request.finish()

        decoder = self.soap_actions[soap_action]
        d = defer.maybeDeferred(decoder, soap_action, soap_data)
        d.addCallbacks(reply, decodeError)

        return server.NOT_DONE_YET



def setupSOAPResource(top_resource, resource_name, subpath=None):

    # Default path: NSI/services/ConnectionService
    if subpath is None:
        subpath = ['NSI', 'services' ]

    ir = top_resource

    for path in subpath:
        if path in ir.children:
            ir = ir.children[path]
        else:
            nr = resource.Resource()
            ir.putChild(path, nr)
            ir = nr

    if resource_name in ir.children:
        raise AssertionError, 'Trying to insert several SOAP resource in same leaf. Go away.'

    soap_resource = SOAPResource()
    ir.putChild(resource_name, soap_resource)
    return soap_resource

