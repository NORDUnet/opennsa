"""
Various SOAP stuff to use when SUDS is broken.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""


# not sure if this is really need anymore
try:
    from xml.etree import cElementTree as ET
except ImportError:
    from xml.etree import ElementTree as ET


SOAP_ENVELOPE_NS        = "http://schemas.xmlsoap.org/soap/envelope/"
XMLSCHEMA_NS            = "http://www.w3.org/2001/XMLSchema-instance"

NSI_DISCOVERY_TYPES_NS  = "http://schemas.ogf.org/nsi/2012/03/discovery/types"



SOAP_ENV                = ET.QName("{%s}Envelope"   % SOAP_ENVELOPE_NS)
SOAP_HEADER             = ET.QName("{%s}Header"     % SOAP_ENVELOPE_NS)
SOAP_BODY               = ET.QName("{%s}Body"       % SOAP_ENVELOPE_NS)

QUERY_NSA_REQUEST       = ET.QName("{%s}queryNsaRequest"    % NSI_DISCOVERY_TYPES_NS)
REQUEST_TYPE            = ET.QName("{%s}requestType"        % NSI_DISCOVERY_TYPES_NS)

QUERY_NSA_RESPONSE      = ET.QName("{%s}queryNsaResponse"   % NSI_DISCOVERY_TYPES_NS)
DISCOVERY               = ET.QName("{%s}discovery"          % NSI_DISCOVERY_TYPES_NS)

NSA_ID                  = ET.QName("{%s}nsaId"              % NSI_DISCOVERY_TYPES_NS)
SOFTWARE_VERSION        = ET.QName("{%s}softwareVersion"    % NSI_DISCOVERY_TYPES_NS)
START_TIME              = ET.QName("{%s}startTime"          % NSI_DISCOVERY_TYPES_NS)
CURRENT_TIME            = ET.QName("{%s}currentTime"        % NSI_DISCOVERY_TYPES_NS)

SERVICES                = ET.QName("{%s}services"           % NSI_DISCOVERY_TYPES_NS)
SERVICE                 = ET.QName("{%s}service"            % NSI_DISCOVERY_TYPES_NS)

DESCRIPTION             = ET.QName("{%s}description"        % NSI_DISCOVERY_TYPES_NS)
VERSIONS                = ET.QName("{%s}versions"           % NSI_DISCOVERY_TYPES_NS)
VERSION                 = ET.QName("{%s}version"            % NSI_DISCOVERY_TYPES_NS)

NAME                    = ET.QName("{%s}name"               % NSI_DISCOVERY_TYPES_NS)
VERSION                 = ET.QName("{%s}version"            % NSI_DISCOVERY_TYPES_NS)
ENDPOINT                = ET.QName("{%s}endpoint"           % NSI_DISCOVERY_TYPES_NS)
WSDL                    = ET.QName("{%s}wsdl"               % NSI_DISCOVERY_TYPES_NS)
URL                     = ET.QName("{%s}url"                % NSI_DISCOVERY_TYPES_NS)



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

    ET.SubElement(envelope, SOAP_HEADER)
    body = ET.SubElement(envelope, SOAP_BODY)

    return envelope, body


def createQueryNSAPayload(request_type='Detailed'):

    #<?xml version="1.0" encoding="UTF-8"?>
    #<SOAP-ENV:Envelope xmlns:ns0="http://schemas.xmlsoap.org/soap/envelope/"
    #                   xmlns:ns1="http://schemas.ogf.org/nsi/2012/03/discovery/types"
    #                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    #                   xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
    #   <SOAP-ENV:Header/>
    #   <ns0:Body>
    #      <ns1:queryNsaRequest>
    #         <requestType>
    #            <requestType>Detailed</requestType>
    #         </requestType>
    #      </ns1:queryNsaRequest>
    #   </ns0:Body>
    #</SOAP-ENV:Envelope>

    envelope, body = createSoapEnvelope()

    query_nsa_request = ET.SubElement(body, QUERY_NSA_REQUEST)
    rt = ET.SubElement(query_nsa_request, REQUEST_TYPE)
    rt.text = request_type

    _indent(envelope)
    return ET.tostring(envelope)



def createQueryNSAResponsePayload(nsaId, softwareVersion, startTime, currentTime, services):
    # only works with one nsa

    envelope, body = createSoapEnvelope()

    qnr = ET.SubElement(body, QUERY_NSA_RESPONSE)

    ndt = ET.SubElement(qnr, DISCOVERY)

    # services []
    #  service[]
    #    - description
    #    - versions[]

    if services:
        svs = ET.SubElement(ndt, SERVICES)
        for service in services:
            sv = ET.SubElement(svs, SERVICE)
            if 'description' in service:
                ET.SubElement(sv, DESCRIPTION).text = 'hi'
            vrs = ET.SubElement(sv, VERSIONS)
            for version in service['versions']:
                print "V", version
                v = ET.SubElement(vrs, VERSION)
                ET.SubElement(v, NAME).text = version['name']
                ET.SubElement(v, VERSION).text = version['version']
                ET.SubElement(v, ENDPOINT).text = version['endpoint']


    ET.SubElement(ndt, NSA_ID).text           = nsaId
    ET.SubElement(ndt, SOFTWARE_VERSION).text = softwareVersion
    ET.SubElement(ndt, START_TIME).text       = startTime
    ET.SubElement(ndt, CURRENT_TIME).text     = currentTime

    _indent(envelope)
    return ET.tostring(envelope)


