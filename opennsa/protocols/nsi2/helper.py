"""
Various helper functions for nsi2 protocol stack.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012)
"""

import StringIO


# don't really fit anywhere, consider cramming them into the bindings
FRAMEWORK_TYPES_NS  = "http://schemas.ogf.org/nsi/2012/03/framework/types"
CONNECTION_TYPES_NS = "http://schemas.ogf.org/nsi/2012/03/connection/types"
PROTO = 'urn:org.ogf.schema.NSIv2'



def export(type_binding, namespace):

    f = StringIO.StringIO()
    type_binding.export(f, 0, namespacedef_='xmlns:tns="%s"' % namespace)
    return f.getvalue()


