# setup opennsa
# someday there will (hopefully) be more here

from opennsa import nsiservice, nsiclient
from opennsa.protocols.jsonrpc import jsonrpc


def createService(network_name, topology_file, proxy):

    client = jsonrpc.JSONRPCNSIClient()
    nsi_service  = nsiservice.NSIService(network_name, proxy, topology_file, client)
    factory = jsonrpc.OpenNSAJSONRPCFactory(nsi_service)
    return factory



def createClient():

    nsi_service_client = nsiclient.NSIServiceClient()
    factory = jsonrpc.OpenNSAJSONRPCFactory(nsi_service_client)

    client = jsonrpc.JSONRPCNSIClient()

    return client, nsi_service_client, factory



