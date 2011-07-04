"""
OpenNSA topology database and parser.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2011)
"""

import json

from opennsa import nsa



class TopologyError(Exception):
    """
    Generic topology error.
    """
    pass



#class Endpoint:
#
#    def __init__(self, name, config, dest=None):
#        self.name = name
#        self.config = config
#        self.dest = dest
#
#
#    def __str__(self):
#        return '%s:%s:%s' % (self.name, self.dest, self.config)
#



#class Network:
#
#    def __init__(self, name, nsa_address, protocol=None):
#        self.name = name
#        self.nsa_address = nsa_address
#        self.protocol = protocol or 'nsa-jsonrpc'
#        self.endpoints = []
#
#
#    def addEndpoint(self, endpoint):
#        self.endpoints.append(endpoint)
#
#
#    def getEndpoint(self, endpoint_name):
#        for ep in self.endpoints:
#            if ep.name == endpoint_name:
#                return ep
#
#        raise TopologyError('No such endpoint (%s)' % (endpoint_name))
#
#
#    def __str__(self):
#        return '%s,%i' % (self.name, len(self.endpoints))



class Link:
    """
    Represent a from a source and destitionation STP, with the endpoints between them.
    """
    def __init__(self, source_stp, dest_stp, endpoint_pairs):
        self.source_stp      = source_stp
        self.dest_stp        = dest_stp
        self.endpoint_pairs  = endpoint_pairs

    def __str__(self):
        eps = ' - '.join( [ '%s:%s = %s:%s' % (ep[0], ep[1], ep[2], ep[3]) for ep in self.endpoint_pairs ] )
        return '%s:%s - %s - %s:%s' % (self.source_stp, eps, self.dest_network, self.dest_stp)



class Topology:

    def __init__(self):
        self.networks = []


    def addNetwork(self, network):
        if network.name in [ n.name for n in self.networks ]:
            raise TopologyError('Network name must be unique (name: %s)' % network.name)

        self.networks.append(network)


    def parseTopology(self, topology_source):

        if isinstance(topology_source, file):
            topology_data = json.load(topology_source)
        elif isinstance(topology_source, str):
            topology_data = json.loads(topology_source)
        else:
            raise TopologyError('Invalid topology source')

        for network_name, network_info in topology_data.items():
            nw = nsa.Network(network_name, network_info['address'], network_info.get('protocol'))
            for epd in network_info.get('endpoints', []):
                dest_stp = None
                if 'dest-network' in epd and 'dest-ep' in epd:
                    dest_stp = nsa.STP( epd['dest-network'], epd['dest-ep'] )
                ep = nsa.NetworkEndpoint(network_name, epd['name'], epd['config'], dest_stp)
                nw.addEndpoint(ep)

            self.addNetwork(nw)


    def getNetwork(self, network_name):
        for network in self.networks:
            if network.name == network_name:
                return network

        raise TopologyError('No network named %s' % network_name)


    def findLinks(self, source_network, source_endpoint, dest_network, dest_endpoint, service_params=None):
        """
        Find possible links between two STPs.
        """
        # check that STPs exist
        snw = self.getNetwork(source_network)
        snw.getEndpoint(source_endpoint)

        dnw = self.getNetwork(dest_network)
        dnw.getEndpoint(dest_endpoint)

        # find endpoint pairs
        #print "FIND LINK", source_network, source_endpoint, dest_network, dest_endpoint

        link_endpoint_pairs = self.findLinkEndpoints(source_network, source_endpoint, dest_network, dest_endpoint)

        links = []
        for lep in link_endpoint_pairs:
            links.append( Link(nsa.STP(source_network, source_endpoint), nsa.STP(dest_network, dest_endpoint), lep ) )

        return links


    def findLinkEndpoints(self, source_network, source_endpoint, dest_network, dest_endpoint, visited_networks=None):

        #print "FIND LINK EPS", source_network, source_endpoint, visited_networks

        snw = self.getNetwork(source_network)
        routes = []

        for ep in snw.endpoints:

            #print "  Link:", ep, dest_network, dest_endpoint

            if ep.dest_stp is None:
                #print "    Rejecting endpoint due to no pairing"
                continue

            if visited_networks is None:
                visited_networks = [ source_network ]

            if ep.dest_stp.network in visited_networks:
                #print "    Rejecting endpoint due to loop"
                continue

            if ep.dest_stp.network == dest_network:
                routes.append( [ ( source_network, ep.endpoint, ep.dest_stp.network, ep.dest_stp.endpoint) ] )
            else:
                nvn = visited_networks[:] + [ ep.dest_stp.network ]
                subroutes = self.findLinkEndpoints(ep.dest_stp.network, ep.dest_stp.endpoint, dest_network, dest_endpoint, nvn)
                if subroutes:
                    for sr in subroutes:
                        src = sr[:]
                        src.insert(0, (source_network, ep.endpoint, ep.dest_stp.network, ep.dest_stp.endpoint) )
                        routes.append(  src  )

        return routes


    def __str__(self):
        return '\n'.join( [ str(n) for n in self.networks ] )

