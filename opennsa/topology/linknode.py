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

from twisted.python import log


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
        for port_name, port in node.ports.items():
            print port_name, '->', port.remote_network, port.remote_port
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



def test():

    na = Node('aruba')
    na.addPort('bon', None, 'bonaire', 'aru')

    nb = Node('bonaire')
    nb.addPort('aru', None, 'aruba', 'bon')
    nb.addPort('cur', None, 'curacao', 'bon')

    nc = Node('curacao')
    nc.addPort('bon', None, 'bonaire', 'cur')

    nd = Node('dominica')

    g = Graph()
    g.addNode(na)
    g.addNode(nb)
    g.addNode(nc)
    g.addNode(nd)

    print g.dijkstra('aruba', 'aruba')
    print g.dijkstra('aruba', 'bonaire')
    print g.dijkstra('aruba', 'curacao')
    print g.dijkstra('bonaire', 'curacao')
    print g.dijkstra('curacao', 'aruba')

    print g.dijkstra('aruba', 'dominica')
    print g.dijkstra('dominica', 'bonaire')


if __name__ == '__main__':
    test()

