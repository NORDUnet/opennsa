"""
Web Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

from twisted.python import log
from twisted.internet import defer
from twisted.web import resource, server

from xml.sax.saxutils import escape as xml_escape



LOG_SYSTEM = 'protocol.SOAPResource'


SERVICE_FAULT = """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
   <SOAP-ENV:Body>
       <SOAP-ENV:Fault>
           <faultcode>SOAP-ENV:Server</faultcode>
           <faultstring>%(fault_string)s</faultstring>
       </SOAP-ENV:Fault>
   </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
"""

SERVICE_FAULT_DETAILED = """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
   <SOAP-ENV:Body>
       <SOAP-ENV:Fault>
           <faultcode>SOAP-ENV:Server</faultcode>
           <faultstring>%(fault_string)s</faultstring>
            <detail>
                %(detail)s
            </detail>
       </SOAP-ENV:Fault>
   </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
"""


# Consider moving this to minisoap sometime
class SOAPFault(Exception):

    def __init__(self, fault_string, detail=None):
        self.fault_string = fault_string
        self.detail = detail


    def createPayload(self):

        # Need to do some escaping

        fault_string = xml_escape( self.fault_string )

        if self.detail is None:
            payload = SERVICE_FAULT % {'fault_string': fault_string }
        else:
            payload = SERVICE_FAULT_DETAILED % {'fault_string': fault_string, 'detail': self.detail }

        print "SERVICE FAULT\n", payload, "\n"
        return payload



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

        def errorReply(err):

            log.msg('Failure during SOAP decoding/dispatch: %s' % err.getErrorMessage(), system=LOG_SYSTEM)

            if err.check(SOAPFault): # is not None:
                print "EC MATCH"
                error_payload = err.value.createPayload()
            else:
                error_payload = SOAPFault(err.getErrorMessage()).createPayload()

            request.setResponseCode(500) # Internal server error
            request.setHeader('Content-Type', 'text/xml')
            request.write(error_payload)
            request.finish()

        decoder = self.soap_actions[soap_action]
        d = defer.maybeDeferred(decoder, soap_data)
        d.addCallbacks(reply, errorReply)

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

