"""
OpenNSA topology representation.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2011-2012)
"""

from opennsa import nsa, error



class Topology:

    def __init__(self):
        self.networks = []


    def addNetwork(self, network):
        if network.name in [ n.name for n in self.networks ]:
            raise error.TopologyError('Network name must be unique (name: %s)' % network.name)

        self.networks.append(network)


    def getNetwork(self, network_name):
        for network in self.networks:
            if network.name == network_name:
                return network

        raise error.TopologyError('No network named %s' % network_name)


    def getEndpoint(self, network, endpoint):

        nw = self.getNetwork(network)
        for ep in nw.endpoints:
            if ep.endpoint == endpoint:
                return ep

        raise error.TopologyError('No endpoint named %s for network %s' % (endpoint, network))


    def findPaths(self, source_stp, dest_stp, bandwidth=None):
        """
        Find possible paths between two endpoints.
        """
        # check that STPs exist
        snw = self.getNetwork(source_stp.network)
        sep = snw.getEndpoint(source_stp.endpoint)

        dnw = self.getNetwork(dest_stp.network)
        dep = dnw.getEndpoint(dest_stp.endpoint)

        # find endpoint pairs
        #print "FIND PATH", source_stp, dest_stp

        if snw == dnw:
            # same network, make direct connection and nothing else
            network_paths = [ [ nsa.Link(sep.network, sep.endpoint, dep.endpoint) ] ]
        else:
            network_paths = self.findPathEndpoints(source_stp, dest_stp)

        if bandwidth is not None:
            network_paths = self.filterBandwidth(network_paths, bandwidth)

        # topology cannot represent vlans properly yet
        # this means that all ports can be matched with all ports internally in a network
        # this is incorrect if the network does not support vlan rewriting
        # currently only netherlight supports vlan rewriting (nov. 2011)
        network_paths = self._pruneMismatchedPorts(network_paths)

        paths = [ nsa.Path(np) for np in network_paths ]

        return paths



    def _pruneMismatchedPorts(self, network_paths):

        def vlan(endpoint):
            vlan_id = [ c for c in endpoint if c.isdigit() ] [-1:]
            if not vlan_id:
                vlan = ord(endpoint[-1])
            else:
                vlan = int(vlan_id[0])
            if vlan > 3:
                vlan -= 4
            return vlan

        def canConnect(link):
            if not link.network.endswith('.ets'):
                return True # not a vlan capable network, STPs can connect
            if link.network == 'northernlight.ets':
                return True # these can do vlan rewrite
            source_vlan = vlan(link.source)
            dest_vlan   = vlan(link.dest)
            return source_vlan == dest_vlan

        isValidRoute = lambda path : all( [ canConnect(link) for link in np ] )
        valid_routes = [ np for np in network_paths if isValidRoute(np) ]
        return valid_routes



    def findPathEndpoints(self, source_stp, dest_stp, visited_networks=None):

        #print "FIND PATH EPS", source_stp, visited_networks

        snw = self.getNetwork(source_stp.network)
        routes = []

        for ep in snw.endpoints:

            #print "  Path:", ep, " ", dest_stp

            if ep.dest_stp is None:
                #print "    Rejecting endpoint due to no pairing"
                continue

            if visited_networks is None:
                visited_networks = [ source_stp.network ]

            if ep.dest_stp.network in visited_networks:
                #print "    Rejecting endpoint due to loop"
                continue

            source_ep = self.getEndpoint(source_stp.network, source_stp.endpoint)

            if ep.dest_stp.network == dest_stp.network:
                sp = nsa.Link(ep.network, source_ep.endpoint, ep.endpoint)
                # this means last network, so we add the last hop
                last_source_ep = self.getEndpoint(ep.dest_stp.network, ep.dest_stp.endpoint)
                last_dest_ep   = self.getEndpoint(dest_stp.network, dest_stp.endpoint)
                sp_end = nsa.Link(last_dest_ep.network, last_source_ep.endpoint, last_dest_ep.endpoint)
                routes.append( [ sp, sp_end ] )
            else:
                nvn = visited_networks[:] + [ ep.dest_stp.network ]
                subroutes = self.findPathEndpoints(ep.dest_stp, dest_stp, nvn)
                if subroutes:
                    for sr in subroutes:
                        src = sr[:]
                        sp = nsa.Link(ep.network, source_ep.endpoint, ep.endpoint)
                        src.insert(0, sp)
                        routes.append(  src  )

        return routes


    def filterBandwidth(self, routes, bandwidth):

        def hasBandwidth(route, bandwidth):
            for link in route:
                if link.source.available_capacity is not None and bandwidth.minimum is not None and link.source.available_capacity < bandwidth.minimum:
                    return False
                if link.dest.available_capacity is not None and bandwidth.minimum is not None and link.dest.available_capacity < bandwidth.minimum:
                    return False
            return True

        filtered_routes = [ route for route in routes if hasBandwidth(route, bandwidth) ]
        return filtered_routes


    def __str__(self):
        return '\n'.join( [ str(n) for n in self.networks ] )

