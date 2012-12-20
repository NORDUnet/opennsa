"""
Various helper functions for nsi2 protocol stack.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012)
"""

import StringIO
from xml.etree import cElementTree as ET

from opennsa import nsa
from opennsa.protocols.nsi2 import headertypes as HT, connectiontypes as CT


# don't really fit anywhere, consider cramming them into the bindings
FRAMEWORK_HEADERS_NS = "http://schemas.ogf.org/nsi/2012/03/framework/headers"
CONNECTION_TYPES_NS  = "http://schemas.ogf.org/nsi/2012/03/connection/types"

NML_ETHERNET_NS      = "http://schemas.ogf.org/nml/2012/10/ethernet#"

PROTO = 'urn:org.ogf.schema.NSIv2'

URN_NETWORK = 'urn:ogf:network:'



ET.register_namespace('ftypes', FRAMEWORK_HEADERS_NS)
ET.register_namespace('ctytes', CONNECTION_TYPES_NS)



def export(type_binding, name, level=0):

    f = StringIO.StringIO()
    type_binding.export(f, level, name_=name)
    return f.getvalue()


def createHeader(correlation_id, requester_nsa_urn, provider_nsa_urn, reply_to=None):

    header = HT.CommonHeaderType(PROTO, correlation_id, requester_nsa_urn, provider_nsa_urn, reply_to)
    header_payload = export(header, 'nsiHeader')
    return header_payload



def createSTP(stp_type):

    if not stp_type.networkId.startswith(URN_NETWORK):
        raise ValueError('STP networkId did not start with %s' % URN_NETWORK)

    network = stp_type.networkId.replace(URN_NETWORK, '')

    if not stp_type.localId.startswith(stp_type.networkId + ':'):
        raise ValueError('STP localId (%s) is not within specified network %s' % (stp_type.localId, stp_type.networkId))

    local_id = stp_type.localId.replace(stp_type.networkId + ':', '')

    labels = [ nsa.Label(tvp.type_, tvp.value[0]) for tvp in stp_type.labels.attribute ]

    return nsa.STP(network, local_id, stp_type.orientation, labels)


def createSTPType(stp, directionality):

    labels = None
    if stp.labels not in (None, []):
        attributes = [ CT.TypeValuePairType(NML_ETHERNET_NS, label.type_, [ label.value ] ) for label in stp.labels ]
        labels = CT.TypeValuePairListType(attributes)

    network = URN_NETWORK + stp.network
    port = stp.endpoint

    return CT.StpType(network, network + ':' + port, labels, directionality)

