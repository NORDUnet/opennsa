"""
OpenNSA Vector path finder (the nordunet-surfnet variant)

Here the word vector means a topology urn and an associated cost.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2011-2014)
"""

LOG_SYSTEM = 'opennsa.topology.gns'



class _NSAVector:

    def __init__(self, cost, topology_urns, vectors):
        assert type(cost) is int, 'cost param must be integer'
        assert cost > 0, 'cost param must be plus-zero'
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

    def __init__(self):

        # this is a set of vectors we keep for each peer
        self.vectors = {} # nsa_urn -> _NSAVector

        # this is the calculated shortest paths, should be recalculated when new information gets available
        self._shortest_paths = {} # topology_urn -> ( nsa_urn, cost)


    def updateVector(self, nsa_urn, nsa_cost, topology_urns, vectors):
        # we need a way to keep the local topology urns out of this

        self.vectors[nsa_urn] = _NSAVector(nsa_cost, topology_urns, vectors)
        self._calculateVectors()


    def deleteVector(self, nsa_urn):
        try:
            self.vectors.pop(nsa_urn)
            self._calculateVectors()
        except KeyError:
            log.msg('Tried to delete non-existing vector for %s' % nsa_urn)


    def _calculateVectors(self):

        paths = {}
        for nsa_urn, nsa_vector in self.vectors.items():
            topo_vectors = nsa_vector.getVectors()

            for topo_urn, cost in topo_vectors.items():
                if not topo_urn in paths:
                    paths[topo_urn] = (nsa_urn, cost)
                elif cost < paths[topo_urn]:
                    paths[topo_urn] = (nsa_urn, cost) # overwrite
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

