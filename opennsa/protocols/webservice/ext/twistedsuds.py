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
from twisted.internet import reactor, defer
from twisted.web import client as twclient
from twisted.internet.error import ConnectionDone

from suds.transport import Transport, TransportError
from suds.options import Options
from suds.reader import DefinitionsReader
from suds.wsdl import Definitions
from suds.client import Factory



DEFAULT_TIMEOUT = 20 # seconds



class RequestError(Exception):
    """
    Raised when a request could not be made or failed in an unexpected way.
    Not rased for 5xx responses.
    """



def _httpRequest(url, soap_action, soap_envelope, timeout=DEFAULT_TIMEOUT, ctx_factory=None):
    # copied from twisted.web.client in order to get access to the
    # factory (which contains response codes, headers, etc)

    if type(url) is not str:
        e = RequestError('URL must be string, not %s' % type(url))
        return defer.fail(e), None

    scheme, host, port, _ = twclient._parse(url)

    factory = twclient.HTTPClientFactory(url, method='POST', postdata=soap_envelope, timeout=timeout)
    factory.noisy = False # stop spewing about factory start/stop

    # fix missing port in header (bug in twisted.web.client)
    if port:
        factory.headers['host'] = host + ':' + str(port)

    factory.headers['Content-Type'] = 'text/xml' # CXF will complain if this is not set
    factory.headers['soapaction'] = soap_action
    factory.headers['Authorization'] = 'Basic bnNpZGVtbzpSaW9QbHVnLUZlc3QyMDExIQ==' # base64.b64encode('nsidemo:RioPlug-Fest2011!')

    if scheme == 'https':
        if ctx_factory is None:
            return defer.fail(RequestError('Cannot perform https request without context factory')), None
        reactor.connectSSL(host, port, factory, ctx_factory)
    else:
        reactor.connectTCP(host, port, factory)

    return factory.deferred, factory



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
                action = soap_action[1:-1].split('/')[-1]
                log.msg('SOAP method invocation failed: %s, URL: %s, Action: %s' % (err.getErrorMessage(), url, action), system='TwistedSUDSClient')
            return err

        method = self._getMethod(method_name)

        # build envelope and get action
        soap_envelope = method.binding.input.get_message(method, args, {})
        soap_envelope = soap_envelope.str().encode('utf-8')
        soap_action = str(method.soap.action)

        short_action = soap_action[1:-1].split('/')[-1]
        log.msg('SOAP Dispatch: URL: %s. Action: %s. Length %s' % (url, short_action, len(soap_envelope)), system='TwistedSUDSClient', debug=True)

        # dispatch
        d, factory = _httpRequest(url, soap_action, soap_envelope, timeout=self.timeout, ctx_factory=self.ctx_factory)
        d.addCallbacks(self._parseResponse, invokeError,
                       callbackArgs=(factory, method, short_action), errbackArgs=(url, soap_action))
        return d


    def _getMethod(self, method_name):
        # one service and port should be enough for everybody
        assert len(self.wsdl.services) == 1
        service = self.wsdl.services[0]

        assert len(service.ports) == 1
        port = service.ports[0]

        # print port.methods.keys()
        method = port.methods[method_name]
        return method


    def _parseResponse(self, response, factory, method, short_action):

        log.msg('Received SOAP response for %s' % short_action, debug=True, system='TwistedSUDSClient')
        if factory.status == '200':
            # this should probably be wrapped in maybeDeferred / try+except to handle and propage WebFault properly
            _, result = method.binding.input.get_reply(method, response)
            return result

        else:
            raise NotImplementedError('non-200 error handling not implemented')

