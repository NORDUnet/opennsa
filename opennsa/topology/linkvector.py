"""
OpenNSA Link vector path finder.

For each demarcation port in the network, a vector is kept of remote networks
that can be reached from the link. Somewhat BGP like.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2011-2015)
"""

from twisted.python import log



LOG_SYSTEM = 'topology'

DEFAULT_MAX_COST = 5



class LinkVector:

    def __init__(self, local_networks=None, blacklist_networks=None, max_cost=DEFAULT_MAX_COST):

        # networks hosted by the local nsa, we want these in the vectors (though not used),
        # but don't want to export/use them in reachability
        self.local_networks = []
        self.blacklist_networks = blacklist_networks if not blacklist_networks is None else []
        self.max_cost = max_cost

        # this is a set of vectors each network -> network mapping
        # most vectors will be direct jumps (cost 1), but OpenNSA has the possiblity to manually
        # augment ports with vectors, and cost, hence it is needed here
        self.vectors = {} # (network, port) -> { network : cost }

        # this is the calculated shortest paths, should be recalculated when vector information changes
        #oself._shortest_paths = {} # network -> (network, port name, cost)
        # calculated shortests path, dijkstra style, but for each network
        self.network_dist = {} # { network : { dest_network : cost } }
        self.network_prev = {} # { network : { dest_network : ( source_network, port) } }

        # update callback subscribers
        self.subscribers = []

        for local_network in local_networks or []:
            self.addLocalNetwork(local_network)


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

        self.network_dist[network] = {}
        self.network_prev[network] = {}

        # recalculate and update
        self._calculateVectors()
        self.updated()


    # -- vector stuff

    def updateVector(self, network, port, vectors):

        if (network, port) in self.vectors:
            np_vectors = self.vectors[network, port]
            for dest_network, cost in vectors.items():
                if dest_network not in np_vectors:
                    log.msg('Add vector {}:{} -> {} {}'.format(network, port, dest_network, cost), system=LOG_SYSTEM)
                    np_vectors[dest_network] = cost
                else:
                    existing_cost = np_vectors[dest_network]
                    if cost != existing_cost:
                        log.msg('Updating vector {}:{} -> {} {} ({})'.format(network, port, dest_network, cost, existing_cost), system=LOG_SYSTEM)
                    else:
                        # skip update as entry is identical, only debug here
                        log.msg('Skiping vector update {}:{} -> {} {} ({})'.format(network, port, dest_network, cost, existing_cost),
                                debug=True, system=LOG_SYSTEM)
        else:
            self.vectors[(network,port)] = vectors
            for dest_network, cost in vectors.items():
                log.msg('Add vector {}:{} -> {} {}'.format(network, port, dest_network, cost), system=LOG_SYSTEM)

        self._calculateVectors()
        self.updated()


    def deleteVector(self, network, port):
        try:
            self.vectors.pop((network, port))
            self._calculateVectors()
        except KeyError:
            log.msg('Tried to delete non-existing vector for %s' % port, system=LOG_SYSTEM)


    def _calculateVectors(self):

        # Do dijkstra for each local network

        for local_network in self.local_networks:
            dist, prev = self._dijkstra(local_network)
            self.network_dist[local_network] = dist
            self.network_prev[local_network] = prev


    def _dijkstra(self, source_network):

        # build unvisisted set, not sure all of these are needed
        unvisited_networks = set()
        unvisited_networks.update(self.local_networks)
        unvisited_networks.update( [ network for network, port in self.vectors.keys() ] )
        for vector in self.vectors.values():
            unvisited_networks.update( vector.keys() )
        # remove source network?

        unvisited_networks -= set(self.blacklist_networks)

        dist = {} # { network : cost }
        prev = {} # { network : (source_network, source_port) }

        while unvisited_networks:

            if not dist:
                u = source_network
                u_cost = 0
            else:
                # FIXME need to check if empty
                cost_network = [ (cost, network) for network, cost in dist.items() if network in unvisited_networks ]
                if not cost_network:
                    return dist, prev # nothing more can be visited
                #cn = min( [ (cost, network) for network, cost in dist.items() if network in unvisited_networks ] )
                #cn = min(cost_network)
                u_cost, u = min(cost_network)

            for port, vectors in [ (port, vectors) for (network, port), vectors in self.vectors.items() if network == u ]:
                for dest_network, cost in vectors.items():
                    if dest_network == source_network:
                        continue # skip routes to source
                    if dest_network in self.blacklist_networks:
                        continue # skip networks in blacklist
                    dest_cost = u_cost + cost
                    if dest_cost > self.max_cost:
                        continue

                    prev_dist = dist.get(dest_network)
                    if prev_dist is None or dest_cost < prev_dist:
                        dist[dest_network] = dest_cost
                        prev[dest_network] = (u, port)
            if u == source_network and not dist:
                return dist, prev

            unvisited_networks.remove(u)

        return dist, prev


    def path(self, network, source):

        # find path from source to network

        if not source in self.local_networks:
            raise ValueError('source {} is not a local network, cannot find path'.format(source))

        if not network in self.network_prev[source]:
            return None

        path = []

        prev = self.network_prev[source]
        prev_network, prev_port = prev[network]
        path.append( (prev_network, prev_port) )
        while prev_network != source:
            prev_network, prev_port = prev[prev_network]
            path.append( (prev_network, prev_port) )

        return list(reversed(path))


    def vector(self, network, source):
        # typical usage for path finding, find the 'vector' (first jump) to the network

        path = self.path(network, source)
        if path is None:
            return None, None
        else:
            return path[0]

