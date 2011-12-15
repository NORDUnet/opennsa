"""
High-level functionality for creating clients and services in OpenNSA.
"""

from opennsa import nsiservice
from opennsa.protocols.webservice import client, service, provider, requester, resource



def createService(network_name, topology_file, backend, host, port, wsdl_dir, ctx_factory=None):

    # reminds an awful lot about client setup

    if ctx_factory:
        proto_scheme = 'https://'
    else:
        proto_scheme = 'http://'
    service_url = proto_scheme + '%s:%i/NSI/services/ConnectionService' % (host,port)

    nsi_resource, site = resource.createService()

    provider_client     = client.ProviderClient(service_url, wsdl_dir, ctx_factory=ctx_factory)
    nsi_requester = requester.Requester(provider_client)
    service.RequesterService(nsi_resource, nsi_requester)

    # now provider service

    nsi_service  = nsiservice.NSIService(network_name, backend, topology_file, nsi_requester)

    requester_client = client.RequesterClient(wsdl_dir)
    nsi_provider = provider.Provider(nsi_service, requester_client)
    service.ProviderService(nsi_resource, nsi_provider)

    return site



def createClient(host, port, wsdl_dir, ctx_factory=None):

    nsi_resource, site = resource.createService()

    # we only support http for callback currently
    service_url = 'http://%s:%i/NSI/services/ConnectionService' % (host,port)

    provider_client     = client.ProviderClient(service_url, wsdl_dir, ctx_factory=ctx_factory)
    nsi_requester = requester.Requester(provider_client, callback_timeout=35)
    service.RequesterService(nsi_resource, nsi_requester)

    return nsi_requester, None, site

