"""
High-level functionality for creating clients and services in OpenNSA.
"""

from opennsa import nsiservice, nsiclient
from opennsa.protocols.jsonrpc import jsonrpc
from opennsa.protocols.webservice import client as wsclient, service as wsservice, provider as wsprovider, requester as wsrequester, resource as wsresource


WEBSERVICE  = 'webservice'
JSONRPC     = 'jsonrpc'
PROTOCOL    = WEBSERVICE



#def _makeClient(protocol, port):
#
#    elif protocol == JSONRPC:
#        return jsonrpc.JSONRPCNSIClient()
#
#def _makeFactory(protocol, nsi_service):
#
#    elif protocol == JSONRPC:
#        return jsonrpc.OpenNSAJSONRPCFactory(nsi_service)


def createService(network_name, topology_file, proxy, port):

    protocol = WEBSERVICE


    if protocol == WEBSERVICE:

        # reminds an awful lot about client setup

        service_url = 'http://localhost:%i/NSI/services/ConnectionService' % port

        resource, site = wsresource.createService()

        provider_client     = wsclient.ProviderClient(service_url)
        requester = wsrequester.Requester(provider_client)
        requester_service   = wsservice.RequesterService(resource, requester)

        # now provider service

        nsi_service  = nsiservice.NSIService(network_name, proxy, topology_file, requester)

        requester_client = wsclient.RequesterClient()
        provider = wsprovider.Provider(nsi_service, requester_client)
        provider_service = wsservice.ProviderService(resource, provider)

        return site

    else:
        raise NotImplementedError('ARG createService')
        client = _makeClient(PROTOCOL, port)
        factory = _makeFactory(PROTOCOL, nsi_service)
        return factory


def createClient(port):

    protocol = WEBSERVICE

    if protocol == WEBSERVICE:

        resource, site = wsresource.createService()

        service_url = 'http://localhost:%i/NSI/services/ConnectionService' % port

        provider_client     = wsclient.ProviderClient(service_url)
        requester = wsrequester.Requester(provider_client, callback_timeout=10)
        requester_service   = wsservice.RequesterService(resource, requester)

        return requester, None, site


    else:
        raise NotImplementedError('ARG')

