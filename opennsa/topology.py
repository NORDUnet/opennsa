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


    def findLinks(self, source_stp, dest_stp, service_params=None):
        """
        Find possible links between two STPs.
        """
        # check that STPs exist
        snw = self.getNetwork(source_stp.network)
        snw.getEndpoint(source_stp.endpoint)

        dnw = self.getNetwork(dest_stp.network)
        dnw.getEndpoint(dest_stp.endpoint)

        # find endpoint pairs
        #print "FIND LINK", source_stp, dest_stp

        link_endpoint_pairs = self.findLinkEndpoints(source_stp, dest_stp)

        links = []
        for lep in link_endpoint_pairs:
            links.append( Link(source_stp, dest_stp, lep ) )

        return links


    def findLinkEndpoints(self, source_stp, dest_stp, visited_networks=None):

        #print "FIND LINK EPS", source_stp, visited_networks

        snw = self.getNetwork(source_stp.network)
        routes = []

        for ep in snw.endpoints:

            #print "  Link:", ep, dest_network, dest_endpoint

            if ep.dest_stp is None:
                #print "    Rejecting endpoint due to no pairing"
                continue

            if visited_networks is None:
                visited_networks = [ source_stp.network ]

            if ep.dest_stp.network in visited_networks:
                #print "    Rejecting endpoint due to loop"
                continue

            if ep.dest_stp.network == dest_stp.network:
                routes.append( [ ( source_stp.network, ep.endpoint, ep.dest_stp.network, ep.dest_stp.endpoint) ] )
            else:
                nvn = visited_networks[:] + [ ep.dest_stp.network ]
                subroutes = self.findLinkEndpoints(ep.dest_stp, dest_stp, nvn)
                if subroutes:
                    for sr in subroutes:
                        src = sr[:]
                        src.insert(0, (source_stp.network, ep.endpoint, ep.dest_stp.network, ep.dest_stp.endpoint) )
                        routes.append(  src  )

        return routes


    def __str__(self):
        return '\n'.join( [ str(n) for n in self.networks ] )

