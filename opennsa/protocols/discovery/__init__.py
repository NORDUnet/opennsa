"""
NSI Discovery protocol setup.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012)
"""

from twisted.web import resource

from opennsa.protocols.shared import resource as soapresource
from opennsa.protocols.discovery import service



def setupDiscoveryService(discoverer, top_resource):

    soap_resource = soapresource.setupSOAPResource(top_resource, 'Discovery')

    ds = service.DiscoverService(soap_resource, discoverer)

