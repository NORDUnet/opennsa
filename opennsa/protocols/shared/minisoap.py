"""
Various SOAP stuff to use when SUDS is broken.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

import StringIO

from xml.etree import cElementTree as ET

from twisted.python import log
from twisted.internet import reactor, defer
from twisted.web import client as twclient
from twisted.internet.error import ConnectionDone


LOG_SYSTEM = 'opennsa.protocols.soap'

DEFAULT_TIMEOUT = 30 # seconds

SOAP_ENVELOPE_NS        = "http://schemas.xmlsoap.org/soap/envelope/"

SOAP_ENV                = ET.QName("{%s}Envelope"   % SOAP_ENVELOPE_NS)
SOAP_HEADER             = ET.QName("{%s}Header"     % SOAP_ENVELOPE_NS)
SOAP_BODY               = ET.QName("{%s}Body"       % SOAP_ENVELOPE_NS)



class RequestError(Exception):
    """
    Raised when a request could not be made or failed in an unexpected way.
    """


def _indent(elem, level=0):
    i = "\n" + level*"   "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "   "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            _indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i



def serializeType(type_value, namespace_def=None):

    f = StringIO.StringIO()
    # type_value.export(f, 0, namespacedef_='xmlns:tns="%s"' % FRAMEWORK_TYPES_NS)
    type_value.export(f, 0, namespacedef_=namespace_def)

    return f.getvalue()



def createSoapEnvelope():

    envelope = ET.Element(SOAP_ENV)
    header = ET.SubElement(envelope, SOAP_HEADER)
    body = ET.SubElement(envelope, SOAP_BODY)

    return envelope, header, body



def createSoapPayload(body_payload=None, header_payload=None):
    # somewhat backwards, but it works

    envelope, header, body = createSoapEnvelope()

    if header_payload is not None:
        header_content = ET.fromstring(header_payload)
        header.append(header_content)

    if body_payload is not None:
        body_content = ET.fromstring(body_payload)
        body.append(body_content)

    _indent(envelope)
    payload = ET.tostring(envelope, 'utf-8')

    return payload



def parseSoapPayload(payload):

    envelope = ET.fromstring(payload)

    assert envelope.tag == SOAP_ENV, 'Top element in soap payload is not SOAP:Envelope'

    header_elements = None

    for ec in envelope:
        if ec.tag == SOAP_HEADER:
            if header_elements is not None:
                raise ValueError('SOAP Payload has multiple header elements')
            header_elements = list(ec)
            continue
        elif ec.tag == SOAP_BODY:
            return header_elements, list(ec)
        else:
            raise ValueError('Invalid entry in SOAP payload: %s' % (ec.tag))

    raise ValueError('SOAP Payload does not have a body')



def httpRequest(url, soap_action, soap_envelope, timeout=DEFAULT_TIMEOUT, ctx_factory=None):
    # copied from twisted.web.client in order to get access to the
    # factory (which contains response codes, headers, etc)

    if type(url) is not str:
        e = RequestError('URL must be string, not %s' % type(url))
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
            return defer.fail(RequestError('Cannot perform https request without context factory')), None
        reactor.connectSSL(host, port, factory, ctx_factory)
    else:
        reactor.connectTCP(host, port, factory)

    def invokeError(err):
        if isinstance(err.value, ConnectionDone):
            pass # these are pretty common when the remote shuts down
        else:
            return err


    factory.deferred.addErrback(invokeError)

    return factory

