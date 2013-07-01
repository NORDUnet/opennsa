"""
Various helper functions for nsi2 protocol stack.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012)
"""

import StringIO
from xml.etree import ElementTree as ET

from twisted.python import log

from opennsa import nsa, error
from opennsa.protocols.shared import minisoap
from opennsa.protocols.nsi2 import bindings


LOG_SYSTEM = 'NSI2.Helper'

# don't really fit anywhere, consider cramming them into the bindings
FRAMEWORK_TYPES_NS   = "http://schemas.ogf.org/nsi/2013/04/framework/types"
FRAMEWORK_HEADERS_NS = "http://schemas.ogf.org/nsi/2013/04/framework/headers"
CONNECTION_TYPES_NS  = "http://schemas.ogf.org/nsi/2013/04/connection/types"

PROTO = 'urn:org.ogf.schema.NSIv2'
URN_NETWORK = 'urn:ogf:network:'


ET.register_namespace('ftypes', FRAMEWORK_TYPES_NS)
ET.register_namespace('header', FRAMEWORK_HEADERS_NS)
ET.register_namespace('ctypes', CONNECTION_TYPES_NS)



def createHeader(requester_nsa_urn, provider_nsa_urn, session_security_attrs=None, reply_to=None, correlation_id=None):

    header = bindings.CommonHeaderType(PROTO, correlation_id, requester_nsa_urn, provider_nsa_urn, reply_to, session_security_attrs)
    header_element = header.xml(bindings.nsiHeader)
    return header_element


def createGenericAcknowledgement(header):

    soap_header = bindings.CommonHeaderType(PROTO, header.correlation_id, header.requester_nsa, header.provider_nsa, None, header.session_security_attrs)
    soap_header_element = soap_header.xml(bindings.nsiHeader)

    generic_confirm = bindings.GenericAcknowledgmentType()
    generic_confirm_element = generic_confirm.xml(bindings.acknowledgment)

    payload = minisoap.createSoapPayload(generic_confirm_element, soap_header_element)
    return payload


def createServiceException(err, provider_nsa, connection_id=None):

    variables = None
    child_exception = None

    if err.check(error.NSIError):
        error_id = err.value.errorId
        #se = bindings.ServiceExceptionType(provider_nsa, connection_id, err.value.errorId, err.getErrorMessage(), variables, child_exception)
    else:
        log.msg('Got a non NSIError exception: %s : %s' % (err.value.__class__.__name__, err.getErrorMessage()), system=LOG_SYSTEM)
        log.msg('Cannot create detailed service exception, defaulting to NSI InternalServerError (00500)', system=LOG_SYSTEM)
        log.err(err)
        error_id = error.InternalServerError.errorId
        #se = bindings.ServiceExceptionType(provider_nsa, connection_id, error.InternalServerError.errorId, err.getErrorMessage(), variables, child_exception)

    se = bindings.ServiceExceptionType(provider_nsa, connection_id, error_id, err.getErrorMessage(), variables, child_exception)

    return se


def parseRequest(soap_data):

    headers, bodies = minisoap.parseSoapPayload(soap_data)

    if headers is None:
        raise ValueError('No header specified in payload')
        #raise resource.SOAPFault('No header specified in payload')

    # more checking here...

    header = bindings.parseElement(headers[0])
    body   = bindings.parseElement(bodies[0])

    nsi_header = nsa.NSIHeader(header.requesterNSA, header.providerNSA, None, header.correlationId, header.replyTo)

    return nsi_header, body


def createLabel(type_value_pair):
    if type_value_pair.targetNamespace:
        label_type = '{%s}%s' % (type_value_pair.targetNamespace, type_value_pair.type_)
    else:
        label_type = type_value_pair.type_
    return nsa.Label(label_type, type_value_pair.value)


def createSTP(stp_type):

    if not stp_type.networkId.startswith(URN_NETWORK):
        raise error.PayloadError('STP networkId (%s) did not start with %s' % (stp_type.networkId, URN_NETWORK))

    network = stp_type.networkId.replace(URN_NETWORK, '')

    if not stp_type.localId.startswith(URN_NETWORK):
        raise error.PayloadError('STP localId (%s) did not start with %s' % (stp_type.localId, URN_NETWORK))

    local_id = stp_type.localId.replace(stp_type.networkId + ':', '')

    if stp_type.labels is not None:
        labels = [ createLabel(tvp) for tvp in stp_type.labels ]
    else:
        labels = []

    return nsa.STP(network, local_id, labels)


def createSTPType(stp):

    def createValue(v1, v2):
        if v1 == v2:
            return str(v1)
        else:
            return str(v1) + '-' + str(v2)

    def splitLabelType(label_type):
        if '{' in label_type:
            ns, tag = label_type.split('}',1)
            ns = ns[1:]
        else:
            ns, tag = None, label_type
        return ns, tag

    labels = None
    if stp.labels not in (None, []):
        labels = []
        for label in stp.labels:
            ns, tag = splitLabelType(label.type_)
            labels.append( bindings.TypeValuePairType(tag, ns, [ label.labelValue() ] ) )

    network = URN_NETWORK + stp.network
    port = stp.port

    return bindings.StpType(network, network + ':' + port, labels)

