from twisted.trial import unittest

from opennsa.topology import gns


ARUBA_NSA       = 'aruba:nsa'
BONAIRE_NSA     = 'bonaire:nsa'
CURACAO_NSA     = 'curacao:nsa'
DOMINICA_NSA    = 'dominica:nsa'

ARUBA_TOPO      = 'aruba:topo'
BONAIRE_TOPO    = 'bonaire:topo'
CURACAO_TOPO    = 'curacao:topo'
DOMINCA_TOPO    = 'dominica:topo'


class GNSTest(unittest.TestCase):

    def setUp(self):

        self.rv = gns.RouteVectors( [] )


    def testBasicPathfindingVector(self):

        self.rv.updateVector(ARUBA_NSA, 1, [ ARUBA_TOPO ], { BONAIRE_TOPO : 1 , CURACAO_TOPO : 2 } )

        self.failUnlessEqual( self.rv.vector(ARUBA_TOPO),   ARUBA_NSA)
        self.failUnlessEqual( self.rv.vector(BONAIRE_TOPO), ARUBA_NSA)
        self.failUnlessEqual( self.rv.vector(CURACAO_TOPO), ARUBA_NSA)

        self.failUnlessEquals( self.rv.listVectors(), {
            ARUBA_TOPO   : 1, BONAIRE_TOPO : 2, CURACAO_TOPO : 3 } )

        self.rv.updateVector(BONAIRE_NSA, 1, [ BONAIRE_TOPO ], { CURACAO_TOPO : 1 } )

        self.failUnlessEqual( self.rv.vector(ARUBA_TOPO),   ARUBA_NSA)
        self.failUnlessEqual( self.rv.vector(BONAIRE_TOPO), BONAIRE_NSA)
        self.failUnlessEqual( self.rv.vector(CURACAO_TOPO), BONAIRE_NSA)

        self.failUnlessEquals( self.rv.listVectors(),
                               { ARUBA_TOPO   : 1, BONAIRE_TOPO : 1, CURACAO_TOPO : 2 } )


    def testLocalNetworkExclusion(self):

        self.rv = gns.RouteVectors( [ BONAIRE_TOPO ] )

        self.rv.updateVector(ARUBA_NSA, 1, [ ARUBA_TOPO ], { BONAIRE_TOPO : 1 , CURACAO_TOPO : 2 } )

        self.failUnlessEqual( self.rv.vector(ARUBA_TOPO),   ARUBA_NSA)
        self.failUnlessEqual( self.rv.vector(BONAIRE_TOPO), None)
        self.failUnlessEqual( self.rv.vector(CURACAO_TOPO), ARUBA_NSA)


