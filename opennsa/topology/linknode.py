"""
The one topology system to rule them all.

This an attempt for a just-the-basics topology system, that can produce both
link-vectors, and work for aggregator in tree mode.

It models nodes (networks) and the links between them. This turns out to simply
be graph and graph searching.

UNIs (User-to-Network-Interfaces) are NOT modelled.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2016)
"""

from opennsa import nsa


LOG_SYSTEM = 'topology.linknode'


# Make Port abstraction


class Port:

    def __init__(self, name, label, remote_network, remote_port):
        self.name = name
        self.label = label
        self.remote_network = remote_network
        self.remote_port = remote_port



class Node:

    def __init__(self, name):
        self.name = name
        self.ports = {}

    def addPort(self, port_name, label, remote_network, remote_port):
        self.ports[port_name] = Port(port_name, label, remote_network, remote_port)



class Graph:

    def __init__(self):
        self.nodes = {}
        self.subscribers = []

    # -- updates

    def callOnUpdate(self, f):
        self.subscribers.append(f)


    def updated(self):
        for f in self.subscribers:
            f()

    # -- graph stuff

    def addNode(self, node):
        # print 'addNode', node.name, node.ports
        if not node.name in self.nodes:
            self.nodes[node.name] = node
            self.updated()


    def findPort(self, from_node, to_node):

        for port in self.nodes[from_node].ports.values():
            if port.remote_network == to_node:
                return port
        else:
            return None


    def dijkstra(self, from_node, to_node):

        dist = {} # node_name -> distance
        prev = {} # node_name -> prev node

        q = set( self.nodes.keys() )

        dist[from_node] = 0

        while q:
            nearest = [ (dist[node], node) for node in q if node in dist ]
            if not nearest:
                break # nothing more to check
            dnn, nearest_neighbor = min(nearest)
            q.remove(nearest_neighbor)

            for nn_neighbor in [ pct.remote_network for pct in self.nodes[nearest_neighbor].ports.values() if pct.remote_network is not None ]:

                dn3 = dnn + 1
                if nn_neighbor not in dist or dn3 < dist[nn_neighbor]:
                    dist[nn_neighbor] = dn3
                    prev[nn_neighbor] = nearest_neighbor

        # this is what dijkstra proper returns, not really useful here though
        #return dist, prev

        # create path from prev
        if to_node in dist:
            path = [ to_node ]
            while path[-1] != from_node:
                path.append( prev[path[-1]] )
            return list(reversed(path))
        else:
            return []



def buildPath(start_stp, end_stp, network_path, graph):
    """
    Bulid a path from source to destination through a series of specified networks
    Typically the list of specified network will be the result of a graph.dijkstra

    Note that is perfectly possible to have holes in the networks, that will
    just be a multi-hop link.
    """

    assert start_stp.network == network_path[0], 'Source network and first hop in network does not match'

    current_stp = start_stp

    path = []

    for next_hop in network_path[1:]:

        demarc_port = graph.findPort(current_stp.network, next_hop)

        dest_stp = nsa.STP(current_stp.network, demarc_port.name,  demarc_port.label)
        path.append(nsa.Link( current_stp, dest_stp))

        # the demarc port label is not really right here, but it works
        current_stp = nsa.STP(next_hop, demarc_port.remote_port, demarc_port.label)

    # add last link
    path.append(nsa.Link( current_stp, end_stp))

    return path

