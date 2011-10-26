"""
High-level functionality for creating clients and services in OpenNSA.
"""

from opennsa import nsiservice
from opennsa.protocols.webservice import client as wsclient, service as wsservice, provider as wsprovider, requester as wsrequester, resource as wsresource


WEBSERVICE  = 'webservice'
JSONRPC     = 'jsonrpc'
PROTOCOL    = WEBSERVICE



def createService(network_name, topology_file, backend, host, port, wsdl_dir, hostcert=None, hostkey=None, ca_dir=None):

    protocol = WEBSERVICE

    if protocol == WEBSERVICE:

        # reminds an awful lot about client setup

        service_url = 'http://%s:%i/NSI/services/ConnectionService' % (host,port)

        resource, site = wsresource.createService()

        if hostcert and hostkey and ca_dir
            from opennsa.protocol.webservice import ctxfactory
            ctx_factory = ContextFactory(hostkey, hostcert, ca_dir)

        provider_client     = wsclient.ProviderClient(service_url, wsdl_dir, ctx_factory=ctx_factory)
        requester = wsrequester.Requester(provider_client)
        requester_service   = wsservice.RequesterService(resource, requester)

        # now provider service

        nsi_service  = nsiservice.NSIService(network_name, backend, topology_file, requester)

        requester_client = wsclient.RequesterClient(wsdl_dir)
        provider = wsprovider.Provider(nsi_service, requester_client)
        provider_service = wsservice.ProviderService(resource, provider)

        return site

    else:
        raise NotImplementedError('Unsupport protocol: %s' % protocol)



def createClient(host, port, wsdl_dir):

    protocol = WEBSERVICE

    if protocol == WEBSERVICE:

        resource, site = wsresource.createService()

        service_url = 'http://%s:%i/NSI/services/ConnectionService' % (host,port)

        provider_client     = wsclient.ProviderClient(service_url, wsdl_dir)
        requester = wsrequester.Requester(provider_client, callback_timeout=20)
        requester_service   = wsservice.RequesterService(resource, requester)

        return requester, None, site

    else:
        raise NotImplementedError('Unsupport protocol: %s' % protocol)

