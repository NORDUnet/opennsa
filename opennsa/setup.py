# setup opennsa
# someday there will (hopefully) be more here

from opennsa import jsonrpc, nsiaggregator



def createFactory(network_name, topology_file, proxy):

    nsi_aggregator  = nsiaggregator.NSIAggregator(network_name, proxy, topology_file)
    factory = jsonrpc.OpenNSAJSONRPCFactory(nsi_aggregator)
    return factory

