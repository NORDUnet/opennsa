"""
SOAP Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2016)
"""

from twisted.python import log
from twisted.internet import defer
from twisted.web import resource, server

from opennsa.shared.requestinfo import RequestInfo
from opennsa.protocols.shared import minisoap



LOG_SYSTEM = 'protocol.SOAPResource'



class SOAPFault(Exception):

    def __init__(self, fault_string, detail_element=None):
        self.fault_string = fault_string
        self.detail_element = detail_element


    def createPayload(self):

        return minisoap.createSoapFault(self.fault_string, self.detail_element)



class SOAPResource(resource.Resource):

    isLeaf = True

    def __init__(self, allowed_hosts=None):
        resource.Resource.__init__(self)
        self.soap_actions = {}
        self.allowed_hosts = allowed_hosts # certificate dns


    def registerDecoder(self, soap_action, decoder):

        self.soap_actions[soap_action] = decoder


    def render_POST(self, request):

        if self.allowed_hosts is not None:
            if not request.isSecure():
                request.setResponseCode(401) # Not Authorized
                log.msg('Rejecting request, not secure (no ssl/tls)', system=LOG_SYSTEM)
                return 'Insecure requests not allowed for this resource\r\n'

            cert = request.transport.getPeerCertificate()
            if not cert:
                request.setResponseCode(401) # Not Authorized
                log.msg('Rejecting request, no client certificate presented', system=LOG_SYSTEM)
                return 'Requests without client certificate not allowed\r\n'

            cert_subject = cert.get_subject()
            log.msg('Certificate subject %s' % cert.get_subject(), system=LOG_SYSTEM)
            host_dn = cert.get_subject().get_components()[-1][1]
            log.msg('Host DN: %s' % host_dn, system=LOG_SYSTEM)

            if not host_dn in self.allowed_hosts:
                request.setResponseCode(401) # Not Authorized
                log.msg('Rejecting request, certificate host dn does not match allowed hosts', system=LOG_SYSTEM)
                return 'Requests without certificate not allowed\r\n'

            request_info = RequestInfo(str(cert_subject), host_dn)

        elif request.isSecure():
            # log certificate subject
            cert = request.transport.getPeerCertificate()
            if cert:
                log.msg('Certificate subject %s' % cert.get_subject(), system=LOG_SYSTEM)

            host_dn = cert.get_subject().get_components()[-1][1]
            request_info = RequestInfo(str(cert.get_subject()), host_dn)

        else:
            request_info = RequestInfo()


        soap_action = request.requestHeaders.getRawHeaders('soapaction',[None])[0]

        soap_data = request.content.read()
        log.msg(" -- Received payload --\n%s\n -- END. Received payload --" % soap_data, system=LOG_SYSTEM, payload=True)

        if not soap_action in self.soap_actions:
            log.msg('Got request with unknown SOAP action: %s' % soap_action, system=LOG_SYSTEM)
            request.setResponseCode(406) # Not acceptable
            return 'Invalid SOAP Action for this resource\r\n'

        log.msg('Received SOAP request. Action: %s. Length: %i' % (soap_action, len(soap_data)), system=LOG_SYSTEM, debug=True)

        def reply(reply_data):

            if type(reply_data) is SOAPFault:
                reply_data = reply_data.createPayload()
                request.setResponseCode(500) # Internal server error

            if reply_data is None or len(reply_data) == 0:
                log.msg('None/empty reply data supplied for SOAPResource. This is probably wrong', system=LOG_SYSTEM)
            else:
                log.msg(" -- Sending response --\n%s\n -- END: Sending response --" % reply_data, system=LOG_SYSTEM, payload=True)

            request.setHeader('Content-Type', 'text/xml') # Keeps some SOAP implementations happy
            request.write(reply_data)
            request.finish()

        def errorReply(err, soap_data):

            log.msg('Failure during SOAP decoding/dispatch: %s' % err.getErrorMessage(), system=LOG_SYSTEM)
            log.err(err)
            log.msg('SOAP Payload that caused error:\n%s\n' % soap_data)
            error_payload = SOAPFault(err.getErrorMessage()).createPayload()

            log.msg(" -- Sending response (fault) --\n%s\n -- END: Sending response (fault) --" % error_payload, system=LOG_SYSTEM, payload=True)

            request.setResponseCode(500) # Internal server error
            request.setHeader('Content-Type', 'text/xml')
            request.write(error_payload)
            request.finish()

        decoder = self.soap_actions[soap_action]
        d = defer.maybeDeferred(decoder, soap_data, request_info)
        d.addCallbacks(reply, errorReply, errbackArgs=(soap_data,))

        return server.NOT_DONE_YET



def setupSOAPResource(top_resource, resource_name, subpath=None, allowed_hosts=None):

    # Default path: NSI/services/{resource_name}
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
        raise AssertionError('Trying to insert several SOAP resource in same leaf. Go away.')

    soap_resource = SOAPResource(allowed_hosts=allowed_hosts)
    ir.putChild(resource_name, soap_resource)
    return soap_resource

