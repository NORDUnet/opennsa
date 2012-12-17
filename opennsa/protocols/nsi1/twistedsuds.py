"""
TwistedSUDS client.

Author: Henrik Thostrup Jensen <htj _at_ nordu.net>
Copyright: NORDUnet (2011)

Licsense: MIT License (same as Twisted)
"""

import os
import urlparse
import StringIO

from twisted.python import log
from twisted.internet.error import ConnectionDone

from opennsa.protocol.shared import httpclient

from suds.transport import Transport, TransportError
from suds.options import Options
from suds.reader import DefinitionsReader
from suds.wsdl import Definitions
from suds.client import Factory



DEFAULT_TIMEOUT = 30 # seconds

LOG_SYSTEM = 'TwistedSUDS'



class FileTransport(Transport):
    """
    File-only transport to plug into SUDS.

    Using this guaranties non-blocking behaviour, but at the expense of not
    supporting stuff imported via http.
    """
    def __init__(self):
        Transport.__init__(self)


    def open(self, request):

        parsed_url = urlparse.urlparse(request.url)
        if parsed_url.scheme != 'file':
            raise TransportError('FileTransport does not support %s as protocol' % parsed_url.scheme, 0)

        path = parsed_url.path
        if not os.path.exists(path):
            raise TransportError('Requested file %s does not exist' % path, None, None)

        # make file object in memory so file cannot be changed
        data = open(path).read()
        return StringIO.StringIO(data)


    def send(self, _):
        raise NotImplementedError('Send not supported in FileTransport.')



class TwistedSUDSClient:

    def __init__(self, wsdl, timeout=DEFAULT_TIMEOUT, ctx_factory=None):

        self.options = Options()
        self.options.transport = FileTransport()

        reader = DefinitionsReader(self.options, Definitions)

        self.wsdl = reader.open(wsdl)
        self.type_factory = Factory(self.wsdl)

        self.timeout = timeout
        self.ctx_factory = ctx_factory


    def createType(self, type_name):
        """
        @args typename: type to create. QNames are specified with {namespace}element syntax.
        """
        return self.type_factory.create(type_name)


    def invoke(self, url, method_name, *args):
        """
        Invoke a SOAP/WSDL action. No getattr/getitem magic, sorry.

        @args url: URL/Endpoint to POST SOAP at.
        @args method_name: SOAP Method to invoke.
        @args *args Argument for SOAP method.
        """
        def invokeError(err, url, soap_action):
            if isinstance(err.value, ConnectionDone):
                pass # these are pretty common when the remote shuts down
            else:
                # response body is in err.value.response
                action = soap_action[1:-1].split('/')[-1]
                log.msg('SOAP method invocation failed: %s. Message: %s. URL: %s. Action: %s' % \
                        (err.getErrorMessage(), err.value.response, url, action), system=LOG_SYSTEM)
            return err

        method = self._getMethod(method_name)

        # build envelope and get action
        soap_envelope = method.binding.input.get_message(method, args, {})
        soap_envelope = soap_envelope.str().encode('utf-8')
        soap_action = str(method.soap.action)

        short_action = soap_action[1:-1].split('/')[-1]
        log.msg('SOAP Dispatch: URL: %s. Action: %s. Length %s' % (url, short_action, len(soap_envelope)), system=LOG_SYSTEM, debug=True)

        # dispatch
        factory = httpclient.httpRequest(url, soap_action, soap_envelope, timeout=self.timeout, ctx_factory=self.ctx_factory)
        factory.deferred.addCallbacks(self._parseResponse, invokeError,
                         callbackArgs=(factory, method, short_action), errbackArgs=(url, soap_action))
        return factory.deferred


    def _getMethod(self, method_name):
        # one service and port should be enough for everybody
        assert len(self.wsdl.services) == 1, 'TwistedSUDSClient can only handle one service'
        service = self.wsdl.services[0]

        assert len(service.ports) == 1, 'TwistedSUDSClient can only handle port'
        port = service.ports[0]

        # print port.methods.keys()
        method = port.methods[method_name]
        return method


    def _parseResponse(self, response, factory, method, short_action):

        log.msg('Received SOAP response for %s' % short_action, debug=True, system=LOG_SYSTEM)
        if factory.status == '200':
            # Note: This can raise suds.WebFault, but it is the responsibility of the caller to handle that
            _, result = method.binding.input.get_reply(method, response)
            return result

        else:
            raise httpclient.HTTPRequestError('Got a non-200 response from the service. Message:\n----\n' + response + '\n----\n')

