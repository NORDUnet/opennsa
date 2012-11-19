"""
Web Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from twisted.python import log
from twisted.internet import defer
from twisted.web import resource, server

from opennsa.protocols.shared import resource as soapresource


# URL for service is http://HOST:PORT/NSI/services/ConnectionService



def createResourceSite():

    # this may seem a bit much, but makes it much simpler to add or change something later
    top_resource = resource.Resource()
    nsi_resource = resource.Resource()
    services_resource = resource.Resource()

    soap_resource = soapresource.SOAPResource()

    top_resource.putChild('NSI', nsi_resource)
    nsi_resource.putChild('services', services_resource)
    services_resource.putChild('ConnectionService', soap_resource)

    site = server.Site(top_resource, logPath='/dev/null')
    return soap_resource, site

