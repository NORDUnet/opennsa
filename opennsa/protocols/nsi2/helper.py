"""
Various helper functions for nsi2 protocol stack.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012)
"""

import StringIO
from xml.etree import cElementTree as ET

from twisted.python import log

from opennsa import nsa, error
from opennsa.protocols.shared import minisoap
from opennsa.protocols.nsi2 import headertypes as HT, connectiontypes as CT


LOG_SYSTEM = 'NSI2.Helper'

# don't really fit anywhere, consider cramming them into the bindings
FRAMEWORK_HEADERS_NS = "http://schemas.ogf.org/nsi/2012/03/framework/headers"
CONNECTION_TYPES_NS  = "http://schemas.ogf.org/nsi/2012/03/connection/types"

NML_ETHERNET_NS      = "http://schemas.ogf.org/nml/2012/10/ethernet#"

PROTO = 'urn:org.ogf.schema.NSIv2'

URN_NETWORK = 'urn:ogf:network:'



ET.register_namespace('ftypes', FRAMEWORK_HEADERS_NS)
ET.register_namespace('ctypes', CONNECTION_TYPES_NS)



def export(type_binding, name, level=0):

    f = StringIO.StringIO()
    type_binding.export(f, level, name_=name)
    return f.getvalue()


def createHeader(correlation_id, requester_nsa_urn, provider_nsa_urn, reply_to=None):

    header = HT.CommonHeaderType(PROTO, correlation_id, requester_nsa_urn, provider_nsa_urn, reply_to)
    header_payload = export(header, 'nsiHeader')
    return header_payload


def createServiceException(err, provider_nsa):

    variables = None

    if err.check(error.NSIError):
        se = CT.ServiceExceptionType(provider_nsa, err.value.errorId, err.getErrorMessage(), variables)
    else:
        log.msg('Got a non NSIError exception, cannot create detailed service exception (%s)' % type(err.value), system=LOG_SYSTEM)
        log.err(err)
        se = CT.ServiceExceptionType(provider_nsa, error.InternalServerError.errorId, err.getErrorMessage(), variables)

    return se


def parseRequest(soap_data, rootClass=None):

    headers, bodies = minisoap.parseSoapPayload(soap_data)

    if headers is None:
        raise ValueError('No header specified in payload')
        #raise resource.SOAPFault('No header specified in payload')

    # more checking here...

    header = HT.parseString( ET.tostring( headers[0] ) )
    body   = CT.parseString( ET.tostring( bodies[0] ), rootClass=rootClass ) # only one body element supported for now

    return header, body


def createSTP(stp_type):

    if not stp_type.networkId.startswith(URN_NETWORK):
        raise ValueError('STP networkId did not start with %s' % URN_NETWORK)

    network = stp_type.networkId.replace(URN_NETWORK, '')

    if not stp_type.localId.startswith(stp_type.networkId + ':'):
        raise ValueError('STP localId (%s) is not within specified network %s' % (stp_type.localId, stp_type.networkId))

    local_id = stp_type.localId.replace(stp_type.networkId + ':', '')

    labels = [ nsa.Label(tvp.type_, tvp.value) for tvp in stp_type.labels.attribute ]

    return nsa.STP(network, local_id, stp_type.orientation, labels)


def createSTPType(stp, directionality):

    def createValue(v1, v2):
        if v1 == v2:
            return v1
        else:
            return str(v1) + '-' + str(v2)

    labels = None
    if stp.labels not in (None, []):
        attributes = [ CT.TypeValuePairType(NML_ETHERNET_NS, label.type_, [ createValue(*v) for v in label.values ] ) for label in stp.labels ]
        labels = CT.TypeValuePairListType(attributes)

    network = URN_NETWORK + stp.network
    port = stp.endpoint

    return CT.StpType(network, network + ':' + port, labels, directionality)

