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

    def __init__(self, local_networks, blacklist_networks=None, max_cost=DEFAULT_MAX_COST):

        # networks hosted by the local nsa, we want these in the vectors (though not used),
        # but don't want to export/use them in reachability
        self.local_networks = local_networks
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

    # -- vector stuff

    def updateVector(self, port, vectors):

        if port in self.vectors:
            self.vectors[port].update(vectors)
        else:
            self.vectors[port] = vectors

        self._calculateVectors()
        self.updated()


    def deleteVector(self, port):
        try:
            self.vectors.pop(port)
            self._calculateVectors()
        except KeyError:
            log.msg('Tried to delete non-existing vector for %s' % port)


    def _calculateVectors(self):

        log.msg('* Calculating shortest-path vectors', debug=True, system=LOG_SYSTEM)
        paths = {}
        for port, vectors in self.vectors.items():

            for network, cost in vectors.items():
                if network in self.local_networks:
                    continue # skip local networks
                if network in self.blacklist_networks:
                    log.msg('Skipping network %s in vector calculation, is blacklisted' % network, system=LOG_SYSTEM)
                    continue
                if cost > self.max_cost:
                    log.msg('Skipping network %s in vector calculation, cost %i exceeds max cost %i' % (network, cost, self.max_cost), system=LOG_SYSTEM)
                    continue
                if not network in paths:
                    paths[network] = (port, cost)
                    log.msg('Added path to %s via %s. Cost %i' % (network, port, cost), debug=True, system=LOG_SYSTEM)
                elif cost < paths[network][1]:
                    paths[network] = (port, cost) # overwrite
                    log.msg('Updated path to %s via %s. Cost %i' % (network, port, cost), debug=True, system=LOG_SYSTEM)
                # no else, it means we have a cheaper path

        self._shortest_paths = paths


    def vector(self, network):
        # typical usage for path finding
        try:
            port, cost = self._shortest_paths[network]
            return port
        except KeyError:
            return None # or do we need an exception here?


    def listVectors(self):
        # needed for exporting topologies
        return { network : cost for (network, (_, cost) ) in self._shortest_paths.items() }

