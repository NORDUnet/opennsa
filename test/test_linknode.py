from twisted.trial import unittest

from opennsa import nsa
from opennsa.topology import linknode



class LinkNodeTest(unittest.TestCase):

    def setUp(self):

        self.graph = linknode.Graph()


    def setUpSimpleTestTopology(self):

        na = linknode.Node('aruba')
        na.addPort('bon', None, 'bonaire', 'aru')

        nb = linknode.Node('bonaire')
        nb.addPort('aru', None, 'aruba', 'bon')
        nb.addPort('cur', None, 'curacao', 'bon')

        nc = linknode.Node('curacao')
        nc.addPort('bon', None, 'bonaire', 'cur')

        nd = linknode.Node('dominica')

        self.graph.addNode(na)
        self.graph.addNode(nb)
        self.graph.addNode(nc)
        self.graph.addNode(nd)


    def testBasicPathfinding(self):

        self.setUpSimpleTestTopology()

        self.failUnlessEqual( self.graph.dijkstra('aruba', 'aruba'), ['aruba'])
        self.failUnlessEqual( self.graph.dijkstra('aruba', 'bonaire'), ['aruba', 'bonaire'] )
        self.failUnlessEqual( self.graph.dijkstra('aruba', 'curacao'), ['aruba', 'bonaire', 'curacao'] )
        self.failUnlessEqual( self.graph.dijkstra('bonaire', 'curacao'), [ 'bonaire', 'curacao' ] )
        self.failUnlessEqual( self.graph.dijkstra('curacao', 'aruba'), ['curacao', 'bonaire', 'aruba'] )

        self.failUnlessEqual( self.graph.dijkstra('aruba', 'dominica'), [])
        self.failUnlessEqual( self.graph.dijkstra('dominica', 'bonaire'), [])


    def testShortPathBuilding(self):

        self.setUpSimpleTestTopology()

        network_path = self.graph.dijkstra('aruba', 'bonaire')

        source = nsa.STP('aruba', 'ps', nsa.Label('vlan', '1'))
        dest = nsa.STP('bonaire', 'ps', nsa.Label('vlan', '1'))

        path = linknode.buildPath(source, dest, network_path, self.graph)

        expected_path = [ nsa.Link(source, nsa.STP('aruba', 'bon', None)),
                          nsa.Link(nsa.STP('bonaire', 'aru', None), dest) ]

        self.failUnlessEqual(path, expected_path)


    def testLongPathBuilding(self):

        self.setUpSimpleTestTopology()

        network_path = self.graph.dijkstra('aruba', 'curacao')

        source = nsa.STP('aruba', 'ps', nsa.Label('vlan', '1'))
        dest = nsa.STP('curacao', 'ps', nsa.Label('vlan', '1'))

        path = linknode.buildPath(source, dest, network_path, self.graph)

        expected_path = [ nsa.Link(source, nsa.STP('aruba', 'bon', None)),
                          nsa.Link(nsa.STP('bonaire', 'aru', None), nsa.STP('bonaire', 'cur', None)),
                          nsa.Link(nsa.STP('curacao', 'bon', None), dest) ]

        self.failUnlessEqual(path, expected_path)


    def testSparsePathBuilding(self):

        self.setUpSimpleTestTopology()

        network_path = [ 'aruba', 'bonaire' ]

        source = nsa.STP('aruba', 'ps', nsa.Label('vlan', '1'))
        dest = nsa.STP('curacao', 'ps', nsa.Label('vlan', '1'))

        path = linknode.buildPath(source, dest, network_path, self.graph)

        expected_path = [ nsa.Link(source, nsa.STP('aruba', 'bon', None)),
                          nsa.Link(nsa.STP('bonaire', 'aru', None), dest) ]

        self.failUnlessEqual(path, expected_path)

