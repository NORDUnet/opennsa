"""
OpenNSA topology database and parser.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2011)
"""

import json

from opennsa import nsa, error



class Topology:

    def __init__(self):
        self.networks = []


    def addNetwork(self, network):
        if network.name in [ n.name for n in self.networks ]:
            raise error.TopologyError('Network name must be unique (name: %s)' % network.name)

        self.networks.append(network)


    def parseTopology(self, topology_source):

        if isinstance(topology_source, file):
            topology_data = json.load(topology_source)
        elif isinstance(topology_source, str):
            topology_data = json.loads(topology_source)
        else:
            raise error.TopologyError('Invalid topology source')

        for network_name, network_info in topology_data.items():
            nn = nsa.NetworkServiceAgent(network_info['address'], protocol=network_info.get('protocol'))
            nw = nsa.Network(network_name, nn)
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

        raise error.TopologyError('No network named %s' % network_name)


    def findPaths(self, source_stp, dest_stp, service_params=None):
        """
        Find possible paths between two STPs.
        """
        # check that STPs exist
        snw = self.getNetwork(source_stp.network)
        snw.getEndpoint(source_stp.endpoint)

        dnw = self.getNetwork(dest_stp.network)
        dnw.getEndpoint(dest_stp.endpoint)

        # find endpoint pairs
        #print "FIND PATH", source_stp, dest_stp

        path_endpoint_pairs = self.findPathEndpoints(source_stp, dest_stp)

        paths = []
        for lep in path_endpoint_pairs:
            paths.append( nsa.Path(source_stp, dest_stp, lep ) )

        return paths


    def findPathEndpoints(self, source_stp, dest_stp, visited_networks=None):

        #print "FIND PATH EPS", source_stp, visited_networks

        snw = self.getNetwork(source_stp.network)
        routes = []

        for ep in snw.endpoints:

            #print "  Path:", ep, dest_network, dest_endpoint

            if ep.dest_stp is None:
                #print "    Rejecting endpoint due to no pairing"
                continue

            if visited_networks is None:
                visited_networks = [ source_stp.network ]

            if ep.dest_stp.network in visited_networks:
                #print "    Rejecting endpoint due to loop"
                continue

            if ep.dest_stp.network == dest_stp.network:
                sp = nsa.STPPair(ep, ep.dest_stp)
                routes.append( [ sp ] )
            else:
                nvn = visited_networks[:] + [ ep.dest_stp.network ]
                subroutes = self.findPathEndpoints(ep.dest_stp, dest_stp, nvn)
                if subroutes:
                    for sr in subroutes:
                        src = sr[:]
                        sp = nsa.STPPair(ep, ep.dest_stp)
                        src.insert(0, sp)
                        routes.append(  src  )

        return routes


    def __str__(self):
        return '\n'.join( [ str(n) for n in self.networks ] )

