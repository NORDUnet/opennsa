"""
Various helper functions for nsi2 protocol stack.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012)
"""

import StringIO
from xml.etree import cElementTree as ET

from opennsa.protocols.nsi2 import headertypes as HT


# don't really fit anywhere, consider cramming them into the bindings
FRAMEWORK_TYPES_NS  = "http://schemas.ogf.org/nsi/2012/03/framework/types"
CONNECTION_TYPES_NS = "http://schemas.ogf.org/nsi/2012/03/connection/types"
PROTO = 'urn:org.ogf.schema.NSIv2'


ET.register_namespace('fw', FRAMEWORK_TYPES_NS)
ET.register_namespace('cs', CONNECTION_TYPES_NS)



def export(type_binding, name):

    f = StringIO.StringIO()
    type_binding.export(f, 0, name_=name)
    return f.getvalue()


def createHeader(correlation_id, requester_nsa_urn, provider_nsa_urn, reply_to=None):

    header = HT.CommonHeaderType(PROTO, correlation_id, requester_nsa_urn, provider_nsa_urn, reply_to)
    header_payload = export(header, 'nsiHeader')
    return header_payload

