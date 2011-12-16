"""
High-level functionality for creating clients and services in OpenNSA.
"""

from opennsa import nsiservice
from opennsa.protocols.webservice import client, service, provider, requester, resource



def _createServiceURL(host, port, ctx_factory=None):

    if ctx_factory:
        proto_scheme = 'https://'
    else:
        proto_scheme = 'http://'

    service_url = proto_scheme + '%s:%i/NSI/services/ConnectionService' % (host,port)
    return service_url



def createService(network_name, topology_file, backend, host, port, wsdl_dir, ctx_factory=None):

    # reminds an awful lot about client setup

    service_url = _createServiceURL(host, port, ctx_factory)
    nsi_resource, site = resource.createService()

    provider_client     = client.ProviderClient(service_url, wsdl_dir, ctx_factory=ctx_factory)
    nsi_requester = requester.Requester(provider_client, 30)
    service.RequesterService(nsi_resource, nsi_requester)

    # now provider service

    nsi_service  = nsiservice.NSIService(network_name, backend, topology_file, nsi_requester)

    requester_client = client.RequesterClient(wsdl_dir)
    nsi_provider = provider.Provider(nsi_service, requester_client)
    service.ProviderService(nsi_resource, nsi_provider)

    return site



def createClient(host, port, wsdl_dir, ctx_factory=None):

    service_url = _createServiceURL(host, port, ctx_factory)
    nsi_resource, site = resource.createService()

    provider_client     = client.ProviderClient(service_url, wsdl_dir, ctx_factory=ctx_factory)
    nsi_requester = requester.Requester(provider_client, callback_timeout=65)
    service.RequesterService(nsi_resource, nsi_requester)

    return nsi_requester, None, site

