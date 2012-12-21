"""
A nice handy HTTP client.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

from twisted.python import log
from twisted.internet import reactor, defer
from twisted.web import client as twclient
from twisted.internet.error import ConnectionDone


LOG_SYSTEM = 'opennsa.protocols.httpclient'

DEFAULT_TIMEOUT = 30 # seconds



class HTTPRequestError(Exception):
    """
    Raised when a request could not be made or failed in an unexpected way.
    """


def httpRequest(url, soap_action, soap_envelope, timeout=DEFAULT_TIMEOUT, ctx_factory=None):
    # copied from twisted.web.client in order to get access to the
    # factory (which contains response codes, headers, etc)

    if type(url) is not str:
        e = HTTPRequestError('URL must be string, not %s' % type(url))
        return defer.fail(e), None

    log.msg(" -- Sending Payload --\n%s\n -- END. Sending Payload --" % soap_envelope, system=LOG_SYSTEM, payload=True)

    scheme, host, port, _ = twclient._parse(url)

    factory = twclient.HTTPClientFactory(url, method='POST', postdata=soap_envelope, timeout=timeout)
    factory.noisy = False # stop spewing about factory start/stop

    # fix missing port in header (bug in twisted.web.client)
    if port:
        factory.headers['host'] = host + ':' + str(port)

    #factory.headers['Content-Type'] = 'text/xml' # CXF will complain if this is not set
    factory.headers['Content-Type'] = 'text/xml; charset=utf-8' # CXF will complain if this is not set
    factory.headers['User-Agent'] = 'OpenNSA/Twisted'
    factory.headers['soapaction'] = soap_action
    factory.headers['Authorization'] = 'Basic bnNpZGVtbzpSaW9QbHVnLUZlc3QyMDExIQ==' # base64.b64encode('nsidemo:RioPlug-Fest2011!')

    if scheme == 'https':
        if ctx_factory is None:
            return defer.fail(HTTPRequestError('Cannot perform https request without context factory')), None
        reactor.connectSSL(host, port, factory, ctx_factory)
    else:
        reactor.connectTCP(host, port, factory)

    def invocationError(err):
        if isinstance(err.value, ConnectionDone):
            pass # these are pretty common when the remote shuts down
        else:
            data = err.value.response
            log.msg(' -- Received Reply (fault) --\n%s\n -- END. Received Reply (fault) --' % data, system=LOG_SYSTEM, payload=True)
            return err

    def logReply(data):
        log.msg(" -- Received Reply --\n%s\n -- END. Received Reply --" % data, system=LOG_SYSTEM, payload=True)
        return data

    factory.deferred.addCallbacks(logReply, invocationError)

    return factory

