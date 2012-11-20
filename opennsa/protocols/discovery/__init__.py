"""
NSI Discovery protocol setup.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012)
"""

from twisted.web import resource

from opennsa.protocols.shared import resource as soapresource
from opennsa.protocols.discovery import service



def setupResource(top_resource, subpath=None):

    # Default path: NSI/services/ConnectionService
    if subpath is None:
        subpath = ['NSI', 'services' ]

    ir = top_resource

    for path in subpath:
        if path in ir.children:
            ir = ir.children[path]
        else:
            nr = resource.Resource()
            ir.putChild(path, nr)

    soap_resource = soapresource.SOAPResource()
    ir.putChild('Discovery', soap_resource)
    return soap_resource



def setupDiscoveryService(discoverer, top_resource, wsdl_dir):

    soap_resource = setupResource(top_resource)
    ds = service.DiscoverService(soap_resource, discoverer, wsdl_dir)

