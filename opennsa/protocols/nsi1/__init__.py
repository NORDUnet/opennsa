"""
NSIv1 Web Service Protocol Modules.

This contains various functionality for setting up protocol stuff.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

from twisted.web import resource, server

from opennsa import registry
from opennsa.protocols.shared import resource as soapresource
from opennsa.protocols.nsi1 import client, service, provider, requester




def createResourceSite():

    # Service path: /NSI/services/ConnectionService

    top_resource = resource.Resource()
    nsi_resource = resource.Resource()
    services_resource = resource.Resource()

    soap_resource = soapresource.SOAPResource()

    top_resource.putChild('NSI', nsi_resource)
    nsi_resource.putChild('services', services_resource)
    services_resource.putChild('ConnectionService', soap_resource)

    site = server.Site(top_resource, logPath='/dev/null')
    return soap_resource, site



def createClientResource(host, port, wsdl_dir, tls=False, ctx_factory=None):

    def _createServiceURL(host, port, tls=False):
        proto_scheme = 'https://' if tls else 'http://'
        service_url = proto_scheme + '%s:%i/NSI/services/ConnectionService' % (host,port)
        return service_url

    service_url = _createServiceURL(host, port, tls)
    nsi_resource, site = createResourceSite()

    provider_client     = client.ProviderClient(service_url, wsdl_dir, ctx_factory=ctx_factory)
    nsi_requester = requester.Requester(provider_client, callback_timeout=65)
    service.RequesterService(nsi_resource, nsi_requester, wsdl_dir)

    return nsi_resource, nsi_requester, site



def createClient(host, port, wsdl_dir, tls=False, ctx_factory=None):

    _, nsi_requester, site = createClientResource(host, port, wsdl_dir, tls, ctx_factory)
    return nsi_requester, site



def createService(nsi_service, service_registry, host, port, wsdl_dir, tls=False, ctx_factory=None):

    nsi_resource, nsi_requester, site = createClientResource(host, port, wsdl_dir, tls, ctx_factory)

    service_registry.registerEventHandler(registry.RESERVE,   nsi_requester.reserve,    registry.NSI1_CLIENT)
    service_registry.registerEventHandler(registry.PROVISION, nsi_requester.provision,  registry.NSI1_CLIENT)
    service_registry.registerEventHandler(registry.RELEASE,   nsi_requester.release,    registry.NSI1_CLIENT)
    service_registry.registerEventHandler(registry.TERMINATE, nsi_requester.terminate,  registry.NSI1_CLIENT)
    service_registry.registerEventHandler(registry.QUERY,     nsi_requester.query,      registry.NSI1_CLIENT)

    requester_client = client.RequesterClient(wsdl_dir, ctx_factory)
    nsi_provider = provider.Provider(service_registry, requester_client)
    service.ProviderService(nsi_resource, nsi_provider, wsdl_dir)

    # add connection list resource in a slightly hacky way
    # this needs to be moved to setup.py and we need to handle our resources better
    from opennsa import viewresource
    vr = viewresource.ConnectionListResource(nsi_service)
    site.resource.children['NSI'].putChild('connections', vr)

    return site

