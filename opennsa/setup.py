# setup opennsa
# someday there will (hopefully) be more here

from opennsa import jsonrpc, nsiservice



def createFactory(network_name, topology_file, proxy):

    nsi_service  = nsiservice.NSIService(network_name, proxy, topology_file)
    factory = jsonrpc.OpenNSAJSONRPCFactory(nsi_service)
    return factory

