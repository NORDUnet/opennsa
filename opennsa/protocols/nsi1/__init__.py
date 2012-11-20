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



def setupResource(top_resource):

    # Service path: /NSI/services/ConnectionService

    nsi_resource = resource.Resource()
    cs_resource = resource.Resource()

    soap_resource = soapresource.SOAPResource()

    top_resource.putChild('NSI', nsi_resource)
    nsi_resource.putChild('services', cs_resource)
    cs_resource.putChild('ConnectionService', soap_resource)

    return soap_resource



def createClientResource(top_resource, host, port, wsdl_dir, tls=False, ctx_factory=None):

    def _createServiceURL(host, port, tls=False):
        proto_scheme = 'https://' if tls else 'http://'
        service_url = proto_scheme + '%s:%i/NSI/services/ConnectionService' % (host,port)
        return service_url

    service_url = _createServiceURL(host, port, tls)

    soap_resource = setupResource(top_resource)

    provider_client = client.ProviderClient(service_url, wsdl_dir, ctx_factory=ctx_factory)
    nsi_requester   = requester.Requester(provider_client, callback_timeout=65)

    service.RequesterService(soap_resource, nsi_requester, wsdl_dir)

    return soap_resource, nsi_requester



def createClient(host, port, wsdl_dir, tls=False, ctx_factory=None):

    top_resource = resource.Resource()
    _, nsi_requester = createClientResource(top_resource, host, port, wsdl_dir, tls, ctx_factory)
    site = server.Site(top_resource, logPath='/dev/null')
    return nsi_requester, site



def setupProvider(nsi_service, top_resource, service_registry, host, port, wsdl_dir, tls=False, ctx_factory=None):

    soap_resource, nsi_requester = createClientResource(top_resource, host, port, wsdl_dir, tls, ctx_factory)

    service_registry.registerEventHandler(registry.RESERVE,   nsi_requester.reserve,    registry.NSI1_CLIENT)
    service_registry.registerEventHandler(registry.PROVISION, nsi_requester.provision,  registry.NSI1_CLIENT)
    service_registry.registerEventHandler(registry.RELEASE,   nsi_requester.release,    registry.NSI1_CLIENT)
    service_registry.registerEventHandler(registry.TERMINATE, nsi_requester.terminate,  registry.NSI1_CLIENT)
    service_registry.registerEventHandler(registry.QUERY,     nsi_requester.query,      registry.NSI1_CLIENT)

    requester_client = client.RequesterClient(wsdl_dir, ctx_factory)
    nsi_provider = provider.Provider(service_registry, requester_client)
    service.ProviderService(soap_resource, nsi_provider, wsdl_dir)



def createService(network, backend, topology, host, port, wsdl_dir, tls=False, ctx_factory=None):
    # this one is typically only used for testing

    top_resource = resource.Resource()
    service_registry = registry.ServiceRegistry()

    from opennsa import nsiservice
    nsi_service = nsiservice.NSIService(network, backend, service_registry, topology)

    setupProvider(nsi_service, top_resource, service_registry, host, port, wsdl_dir, tls, ctx_factory)

    factory = server.Site(top_resource, logPath='/dev/null')
    return factory

