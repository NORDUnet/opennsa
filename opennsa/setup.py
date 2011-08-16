"""
High-level functionality for creating clients and services in OpenNSA.
"""

from opennsa import nsiservice, nsiclient
from opennsa.protocols.jsonrpc import jsonrpc
from opennsa.protocols.webservice import client as wsclient, service as wsservice


WEBSERVICE  = 'webservice'
JSONRPC     = 'jsonrpc'
PROTOCOL    = WEBSERVICE



def _makeClient(protocol, port):

    if protocol == WEBSERVICE:
        service_url = 'http://localhost:%i/NSI/services/ConnectionService' % port
        return wsclient.NSIWebServiceClient(service_url)
    elif protocol == JSONRPC:
        return jsonrpc.JSONRPCNSIClient()
    else:
        raise ValueError('Invalid protocol specified')


def _makeFactory(protocol, nsi_service):

    if protocol == WEBSERVICE:
        return wsservice.createNSIWSService(nsi_service)
    elif protocol == JSONRPC:
        return jsonrpc.OpenNSAJSONRPCFactory(nsi_service)
    else:
        raise ValueError('Invalid protocol specified')


def createService(network_name, topology_file, proxy, port):

    client = _makeClient(PROTOCOL, port)
    nsi_service  = nsiservice.NSIService(network_name, proxy, topology_file, client)
    factory = _makeFactory(PROTOCOL, nsi_service)

    return factory


def createClient(port):

    service_url = 'http://localhost:%i/NSI/services/ConnectionService' % port

    client      = _makeClient(PROTOCOL, port)
    nsi_service = nsiclient.NSIServiceClient()
    factory     = _makeFactory(PROTOCOL, nsi_service)

    return client, nsi_service, factory

