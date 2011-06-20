# setup opennsa
# someday there will (hopefully) be more here

from opennsa import jsonrpc, nsirouter



def createFactory(network_name, proxy):

    nsi_aggregator  = nsirouter.NSIRouter(network_name, proxy)
    factory = jsonrpc.OpenNSAJSONRPCFactory(nsi_aggregator)
    return factory

