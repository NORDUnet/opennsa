"""
Various helper functions for nsi2 protocol stack.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012)
"""

from xml.etree import ElementTree as ET

from twisted.python import log, failure

from opennsa import constants as cnt, nsa, error
from opennsa.protocols.shared import minisoap
from opennsa.protocols.nsi2.bindings import nsiframework, nsiconnection


LOG_SYSTEM = 'NSI2.Helper'

# don't really fit anywhere, consider cramming them into the bindings
FRAMEWORK_TYPES_NS   = "http://schemas.ogf.org/nsi/2013/12/framework/types"
FRAMEWORK_HEADERS_NS = "http://schemas.ogf.org/nsi/2013/12/framework/headers"
CONNECTION_TYPES_NS  = "http://schemas.ogf.org/nsi/2013/12/connection/types"
SERVICE_TYPES_NS     = 'http://schemas.ogf.org/nsi/2013/12/services/types'
P2PSERVICES_TYPES_NS = 'http://schemas.ogf.org/nsi/2013/12/services/point2point'

URN_NETWORK = 'urn:ogf:network:'

ET.register_namespace('ftypes', FRAMEWORK_TYPES_NS)
ET.register_namespace('header', FRAMEWORK_HEADERS_NS)
ET.register_namespace('ctypes', CONNECTION_TYPES_NS)
ET.register_namespace('stypes', SERVICE_TYPES_NS)
ET.register_namespace('p2psrv', P2PSERVICES_TYPES_NS)

# Lookup table for urn label
LABEL_MAP = {
    'vlan' : cnt.ETHERNET_VLAN
}



def createProviderHeader(requester_nsa_urn, provider_nsa_urn, reply_to=None, correlation_id=None, security_attributes=None, connection_trace=None):
    return _createHeader(requester_nsa_urn, provider_nsa_urn, reply_to, correlation_id, security_attributes, connection_trace, protocol_type=cnt.CS2_PROVIDER)


def createRequesterHeader(requester_nsa_urn, provider_nsa_urn, reply_to=None, correlation_id=None, security_attributes=None, connection_trace=None):
    return _createHeader(requester_nsa_urn, provider_nsa_urn, reply_to, correlation_id, security_attributes, connection_trace, protocol_type=cnt.CS2_REQUESTER)


def _createHeader(requester_nsa_urn, provider_nsa_urn, reply_to=None, correlation_id=None, security_attributes=None, connection_trace=None, protocol_type=None):

    if protocol_type is None:
        raise AssertionError('Requester or provider protocol type must be specified')

    sat = []
    if security_attributes:
        # group by name to adhere to gns spec
        grouped_sats = {}
        for sa in security_attributes:
            grouped_sats.setdefault(sa.type_, []).append(sa.value)

        for name, values in grouped_sats.items():
            at = nsiframework.AttributeType(name, None, None, values )
            sat.append( nsiframework.SessionSecurityAttrType( [ at ] ) )

    header = nsiframework.CommonHeaderType(protocol_type, correlation_id, requester_nsa_urn, provider_nsa_urn, reply_to, sat, connection_trace)
    header_element = header.xml(nsiframework.nsiHeader)
    return header_element



def createGenericProviderAcknowledgement(header):
    return _createGenericAcknowledgement(header, cnt.CS2_PROVIDER)


def createGenericRequesterAcknowledgement(header):
    return _createGenericAcknowledgement(header, cnt.CS2_REQUESTER)


def _createGenericAcknowledgement(header, protocol_type=None):

    # we do not put reply to, security attributes or connection traces in the acknowledgement
    soap_header_element = _createHeader(header.requester_nsa, header.provider_nsa, correlation_id=header.correlation_id, protocol_type=protocol_type)

    generic_confirm = nsiconnection.GenericAcknowledgmentType()
    generic_confirm_element = generic_confirm.xml(nsiconnection.acknowledgment)

    payload = minisoap.createSoapPayload(generic_confirm_element, soap_header_element)
    return payload



def createServiceException(err, provider_nsa, connection_id=None, service_type=None):

    if isinstance(err, failure.Failure):
        err = err.value # hack on :-)

    if isinstance(err, error.NSIError):
        # use values from error
        variables = [ nsiframework.TypeValuePairType(variable, None, [ str(value) ]) for (variable, value) in err.variables ] if err.variables else None
        return nsiframework.ServiceExceptionType(err.nsaId or provider_nsa, err.connectionId or connection_id,
                                                 service_type, err.errorId, err.message, variables, None)
    else:
        log.msg('Got a non NSIError exception: %s : %s' % (err.__class__.__name__, str(err)), system=LOG_SYSTEM)
        log.msg('Cannot create detailed service exception, defaulting to NSI InternalServerError (00500)', system=LOG_SYSTEM)
        log.err(err)
        error_id = error.InternalServerError.errorId
        return nsiframework.ServiceExceptionType(provider_nsa, connection_id, service_type, error_id, str(err), None, None)



def createException(service_exception, provider_nsa):
    # nsiconnection.ServiceException (binding) -> error.NSIError

    try:
        exception_type = error.lookup(service_exception.errorId)
        variables = [ (tvp.type, tvp.value) for tvp in service_exception.variables ] if service_exception.variables else None
        ex = exception_type(service_exception.text, service_exception.nsaId or provider_nsa, service_exception.connectionId, variables)
    except AssertionError as e:
        log.msg('Error looking up error id: %s. Message: %s' % (service_exception.errorId, str(e)), system=LOG_SYSTEM)
        ex = error.InternalServerError(service_exception.text)

    return ex



def parseRequest(soap_data):

    headers, bodies = minisoap.parseSoapPayload(soap_data)

    if headers is None:
        raise ValueError('No header specified in payload')
    elif len(headers) > 1:
        raise ValueError('Multiple headers specified in payload')

    header = nsiframework.parseElement(headers[0])
    security_attributes = []
    if header.sessionSecurityAttr:
        for ssa in header.sessionSecurityAttr:
            for attr in ssa.Attributes:
                for av in attr.AttributeValue:
                    if av is None:
                        continue
                    security_attributes.append( nsa.SecurityAttribute(attr.Name, av) )

    #if header.protocolVersion not in [ cnt.CS2_REQUESTER, cnt.CS2_PROVIDER ]:
    #    raise ValueError('Invalid protocol "%s". Only %s supported' % (header.protocolVersion, cnt.CS2_SERVICE_TYPE))

    if len(bodies) == 0:
        body = None
    elif len(bodies) == 1:
        body = nsiconnection.parseElement(bodies[0])
    else:
        body = [ nsiconnection.parseElement(b) for b in bodies ]

    nsi_header = nsa.NSIHeader(header.requesterNSA, header.providerNSA, header.correlationId, header.replyTo,
                               security_attributes=security_attributes, connection_trace=header.connectionTrace)

    return nsi_header, body


def parseLabel(label_part):
    if not '=' in label_part:
        raise error.PayloadError('No = in urn label part (%s)' % label_part)

    label_short_type, label_value = label_part.split('=')
    try:
        label_type = LABEL_MAP[label_short_type]
    except KeyError:
        raise error.PayloadError('Label type %s not recognized')

    return nsa.Label(label_type, label_value)



def createSTP(stp_id):

    if not stp_id.startswith(URN_NETWORK):
        raise error.PayloadError('STP Id (%s) did not start with %s' % (stp_id, URN_NETWORK))

    tsi = stp_id.replace(URN_NETWORK, '')

    if '?' in tsi:
        loc, lbp = tsi.split('?')
        label = parseLabel(lbp)
    else:
        loc = tsi
        label = None

    if not ':' in loc:
        raise error.PayloadError('No : in stp urn (%s)' % loc)

    network, port = loc.rsplit(':', 1)

    return nsa.STP(network, port, label)

