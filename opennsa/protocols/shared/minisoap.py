"""
Various SOAP stuff to use when SUDS is broken.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

from xml.etree import ElementTree as ET


LOG_SYSTEM = 'opennsa.protocols.soap'

SOAP_ENVELOPE_NS        = "http://schemas.xmlsoap.org/soap/envelope/"

SOAP_ENV                = ET.QName("{%s}Envelope"   % SOAP_ENVELOPE_NS)
SOAP_HEADER             = ET.QName("{%s}Header"     % SOAP_ENVELOPE_NS)
SOAP_BODY               = ET.QName("{%s}Body"       % SOAP_ENVELOPE_NS)
SOAP_FAULT              = ET.QName("{%s}Fault"      % SOAP_ENVELOPE_NS)

FAULTCODE               = 'faultcode'
FAULTSTRING             = 'faultstring'
DETAIL                  = 'detail'

FAULTCODE_SERVER        = 'soap:Server' # must match with the namespace below

ET.register_namespace('soap', SOAP_ENVELOPE_NS)



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



def createSoapEnvelope():

    envelope = ET.Element(SOAP_ENV)
    header = ET.SubElement(envelope, SOAP_HEADER)
    body = ET.SubElement(envelope, SOAP_BODY)

    return envelope, header, body



def createSoapPayload(body_element=None, header_element=None):

    envelope, header, body = createSoapEnvelope()

    if header_element is not None:
        header.append(header_element)
    if body_element is not None:
        if type(body_element) is list:
            body.extend(body_element)
        else:
            body.append(body_element)

    _indent(envelope)
    payload = ET.tostring(envelope, 'utf-8')

    return payload


def createSoapFault(fault_msg, detail_element=None):

    assert type(fault_msg) is str, 'Fault message must be a string'

#       <SOAP-ENV:Fault>
#           <faultcode>SOAP-ENV:Server</faultcode>
#           <faultstring>%(fault_string)s</faultstring>
#            <detail>
#                %(detail)s
#            </detail>
#       </SOAP-ENV:Fault>

    fault_element = ET.Element(SOAP_FAULT)

    fault_code = ET.SubElement(fault_element, FAULTCODE)
    fault_code.text = FAULTCODE_SERVER

    fault_string = ET.SubElement(fault_element, FAULTSTRING)
    fault_string.text = fault_msg

    if detail_element is not None:
        dec = ET.SubElement(fault_element, DETAIL)
        dec.append(detail_element)


    payload = createSoapPayload(fault_element)
    return payload



def parseSoapPayload(payload):

    envelope = ET.fromstring(payload)

    assert envelope.tag == SOAP_ENV, 'Top element in soap payload is not SOAP:Envelope (got %s)' % envelope.tag

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


def parseFault(payload):

    envelope = ET.fromstring(payload)

    if envelope.tag != SOAP_ENV:
        raise ValueError('Top element in soap payload is not SOAP:Envelope')

    # no header parsing for now

    body = envelope.find( str(SOAP_BODY) )
    if body is None:
        raise ValueError('Fault payload has no SOAP:Body element in SOAP:Envelope')

    fault = body.find( str(SOAP_FAULT) )
    if fault is None:
        raise ValueError('Fault payload has no SOAP:Fault element in SOAP:Body')

    # only SOAP 1.1 for now
    fault_code = fault.find('faultcode')
    if fault_code is None:
        raise ValueError('Fault payload has no faultcode element in SOAP:Fault')

    fault_string = fault.find('faultstring')
    if fault_string is None:
        raise ValueError('Fault payload has no faultstring element in SOAP:Fault')

    detail = None

    dt = fault.find('detail')
    if dt is not None:
        dc = dt.getchildren()[0]
        if dc is not None:
            detail = ET.tostring(dc)

    return fault_code.text, fault_string.text, detail




