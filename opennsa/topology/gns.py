"""
OpenNSA Vector path finder (the nordunet-surfnet variant)

Here the word vector means a topology urn and an associated cost.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2011-2014)
"""

from twisted.python import log



LOG_SYSTEM = 'topology.gns'

DEFAULT_MAX_COST = 5



class _NSAVector:

    def __init__(self, cost, topology_urns, vectors):
        assert type(cost) is int, 'cost param must be integer'
        assert cost >= 0, 'cost param must be plus-zero'
        assert type(topology_urns) is list, 'topology urns must be a list'
        assert type(vectors) is dict, 'reachable_urns_cost must be a dict'
        self.cost = cost
        self.topology_urns = topology_urns
        self.vectors = vectors


    def getVectors(self):
        vectors = {}
        for topo_urn, vcost in self.vectors.items():
            vectors[topo_urn] = self.cost + vcost
        for topo_urn in self.topology_urns:
            vectors[topo_urn] = self.cost
        return vectors



class RouteVectors:

    def __init__(self, local_networks, blacklist_networks=None, max_cost=DEFAULT_MAX_COST):

        # networks hosted by the nsa itself, we want these in the vectors (though currently not used for anything),
        # but don't want to export/use them in reachability
        self.local_networks = local_networks
        self.blacklist_networks = blacklist_networks if not blacklist_networks is None else []
        self.max_cost = max_cost

        # this is a set of vectors we keep for each peer
        self.vectors = {} # nsa_urn -> _NSAVector

        # this is the calculated shortest paths, should be recalculated when new information gets available
        self._shortest_paths = {} # topology_urn -> ( nsa_urn, cost)

        self.subscribers = []

    # -- updates

    def callOnUpdate(self, f):
        self.subscribers.append(f)


    def updated(self):
        for f in self.subscribers:
            f()

    # -- vector stuff

    def getProvider(self, topology_urn):

        for nsa_urn, nsa_vector in self.vectors.items():
            if topology_urn in nsa_vector.topology_urns:
                return nsa_urn


    def updateVector(self, nsa_urn, nsa_cost, topology_urns, vectors):
        # we need a way to keep the local topology urns out of this

        self.vectors[nsa_urn] = _NSAVector(nsa_cost, topology_urns, vectors)
        self._calculateVectors()
        self.updated()


    def deleteVector(self, nsa_urn):
        try:
            self.vectors.pop(nsa_urn)
            self._calculateVectors()
        except KeyError:
            log.msg('Tried to delete non-existing vector for %s' % nsa_urn)


    def _calculateVectors(self):

        log.msg(' * Calculating shortest-path vectors', debug=True, system=LOG_SYSTEM)
        paths = {}
        for nsa_urn, nsa_vector in self.vectors.items():
            topo_vectors = nsa_vector.getVectors()

            for topo_urn, cost in topo_vectors.items():
                if topo_urn in self.local_networks:
                    continue # skip local networks
                if topo_urn in self.blacklist_networks:
                    log.msg('Skipping network %s in vector calculation, is blacklisted' % topo_urn, system=LOG_SYSTEM)
                    continue
                if cost > self.max_cost:
                    log.msg('Skipping network %s in vector calculation, cost %i exceeds max cost %i' % (topo_urn, cost, self.max_cost), system=LOG_SYSTEM)
                    continue
                if not topo_urn in paths:
                    paths[topo_urn] = (nsa_urn, cost)
                    log.msg('Added path to %s via %s. Cost %i' % (topo_urn, nsa_urn, cost), debug=True, system=LOG_SYSTEM)
                elif cost < paths[topo_urn][1]:
                    paths[topo_urn] = (nsa_urn, cost) # overwrite
                    log.msg('Updated path to %s via %s. Cost %i' % (topo_urn, nsa_urn, cost), debug=True, system=LOG_SYSTEM)
                # no else, it means we have a cheaper path

        self._shortest_paths = paths


    def vector(self, topology_urn):
        # typical usage for path finding
        try:
            nsa_urn, cost = self._shortest_paths[topology_urn]
            return nsa_urn
        except KeyError:
            return None # or do we need an exception here?


    def listVectors(self):
        # needed for exporting topologies
        return { topo : cost for (topo, (_, cost) ) in self._shortest_paths.items() }

