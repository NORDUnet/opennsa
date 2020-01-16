"""
OpenNSA Link vector path finder.

For each demarcation port in the network, a vector is kept of remote networks
that can be reached from the link. Somewhat BGP like.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2011-2015)
"""

from twisted.python import log



LOG_SYSTEM = 'topology.linkvector'

DEFAULT_MAX_COST = 5



class LinkVector:

    def __init__(self, local_networks=None, blacklist_networks=None, max_cost=DEFAULT_MAX_COST):

        # networks hosted by the local nsa, we want these in the vectors (though not used),
        # but don't want to export/use them in reachability
        self.local_networks = local_networks or []
        self.blacklist_networks = blacklist_networks if not blacklist_networks is None else []
        self.max_cost = max_cost

        # this is a set of vectors we keep for each peer
        self.vectors = {} # port name -> { network : cost }

        # this is the calculated shortest paths, should be recalculated when new information gets available
        self._shortest_paths = {} # network -> ( port name, cost)

        self.subscribers = []

    # -- updates

    def callOnUpdate(self, f):
        self.subscribers.append(f)


    def updated(self):
        for f in self.subscribers:
            f()

    # -- local networks

    def localNetworks(self):
        return self.local_networks[:]


    def addLocalNetwork(self, network):
        if network in self.local_networks:
            raise ValueError('network {} already exists in local network, refusing to add twice'.format(network))
        self.local_networks.append(network)

        # recalculate and update
        self._calculateVectors()
        self.updated()


    # -- vector stuff

    def updateVector(self, network, port, vectors):

        if (network, port) in self.vectors:
            self.vectors[(network,port)].update(vectors)
        else:
            self.vectors[(network,port)] = vectors

        self._calculateVectors()
        self.updated()


    def deleteVector(self, network, port):
        try:
            self.vectors.pop((network, port))
            self._calculateVectors()
        except KeyError:
            log.msg('Tried to delete non-existing vector for %s' % port)


    def _calculateVectors(self):

        log.msg('* Calculating shortest-path vectors', debug=True, system=LOG_SYSTEM)
        paths = {}
        for (network, port), vectors in self.vectors.items():

            for dest_network, cost in vectors.items():
                if network not in self.local_networks and dest_network in self.local_networks:
                    continue # skip paths to local networks from remote networks
                if dest_network in self.blacklist_networks:
                    log.msg('Skipping network %s in vector calculation, is blacklisted' % dest_network, system=LOG_SYSTEM)
                    continue
                if cost > self.max_cost:
                    log.msg('Skipping network %s in vector calculation, cost %i exceeds max cost %i' % (dest_network, cost, self.max_cost), system=LOG_SYSTEM)
                    continue
                if not dest_network in paths:
                    paths[dest_network] = (network, port, cost)
                    log.msg('Added path to {} via {}:{}, cost {}'.format(dest_network, network, port, cost), debug=True, system=LOG_SYSTEM)
                elif cost < paths[dest_network][2]:
                    paths[dest_network] = (network, port, cost) # overwrite
                    log.msg('Updated path to {} via {}:{}, cost {}'.format(dest_network, network, port, cost), debug=True, system=LOG_SYSTEM)
                # no else, it means we have a cheaper path

        self._shortest_paths = paths


    def vector(self, network):
        # typical usage for path finding
        try:
            network, port, cost = self._shortest_paths[network]
            return network, port
        except KeyError:
            return None,None # or do we need an exception here?


    def listVectors(self):
        # needed for exporting topologies
        return { network : cost for (network, (_, _, cost) ) in self._shortest_paths.items() }

