from twisted.trial import unittest

from opennsa.topology import linkvector


ARUBA_PORT       = 'aruba'
BONAIRE_PORT     = 'bonaire'
CURACAO_PORT     = 'curacao'
DOMINICA_PORT    = 'dominica'

LOCAL_TOPO      = 'local:topo'
ARUBA_TOPO      = 'aruba:topo'
BONAIRE_TOPO    = 'bonaire:topo'
CURACAO_TOPO    = 'curacao:topo'
DOMINCA_TOPO    = 'dominica:topo'


class GNSTest(unittest.TestCase):

    def setUp(self):

        self.rv = linkvector.LinkVector( [ LOCAL_TOPO ] )


    def testBasicPathfindingVector(self):

        self.rv.updateVector(ARUBA_PORT, { ARUBA_TOPO : 1, BONAIRE_TOPO : 2 , CURACAO_TOPO : 3 } )

        self.failUnlessEqual( self.rv.vector(ARUBA_TOPO),   ARUBA_PORT)
        self.failUnlessEqual( self.rv.vector(BONAIRE_TOPO), ARUBA_PORT)
        self.failUnlessEqual( self.rv.vector(CURACAO_TOPO), ARUBA_PORT)

        self.failUnlessEquals( self.rv.listVectors(), { ARUBA_TOPO   : 1, BONAIRE_TOPO : 2, CURACAO_TOPO : 3 } )

        self.rv.updateVector(BONAIRE_PORT, { BONAIRE_TOPO: 1, CURACAO_TOPO : 2 } )

        self.failUnlessEqual( self.rv.vector(ARUBA_TOPO),   ARUBA_PORT)
        self.failUnlessEqual( self.rv.vector(BONAIRE_TOPO), BONAIRE_PORT)
        self.failUnlessEqual( self.rv.vector(CURACAO_TOPO), BONAIRE_PORT)

        self.failUnlessEquals( self.rv.listVectors(), { ARUBA_TOPO   : 1, BONAIRE_TOPO : 1, CURACAO_TOPO : 2 } )


    def testLocalNetworkExclusion(self):

        self.rv = linkvector.LinkVector( [ BONAIRE_TOPO ] )

        self.rv.updateVector(ARUBA_PORT, { ARUBA_TOPO : 1, BONAIRE_TOPO : 1, CURACAO_TOPO : 2 } )

        self.failUnlessEqual( self.rv.vector(ARUBA_TOPO),   ARUBA_PORT)
        self.failUnlessEqual( self.rv.vector(BONAIRE_TOPO), None)
        self.failUnlessEqual( self.rv.vector(CURACAO_TOPO), ARUBA_PORT)


    def testBlackList(self):

        self.rv = linkvector.LinkVector( [ BONAIRE_TOPO ], blacklist_networks = [ CURACAO_TOPO ] )

        self.rv.updateVector(ARUBA_PORT, { ARUBA_TOPO : 1, BONAIRE_TOPO : 1 , CURACAO_TOPO : 2 } )

        self.failUnlessEqual( self.rv.vector(ARUBA_TOPO),   ARUBA_PORT)
        self.failUnlessEqual( self.rv.vector(BONAIRE_TOPO), None)
        self.failUnlessEqual( self.rv.vector(CURACAO_TOPO), None)


    def testMaxCost(self):

        self.rv = linkvector.LinkVector( [ BONAIRE_TOPO ], max_cost=3 )

        self.rv.updateVector(ARUBA_PORT, { ARUBA_TOPO : 1, BONAIRE_TOPO : 1 , CURACAO_TOPO : 4 } )

        self.failUnlessEqual( self.rv.vector(ARUBA_TOPO),   ARUBA_PORT)
        self.failUnlessEqual( self.rv.vector(BONAIRE_TOPO), None)
        self.failUnlessEqual( self.rv.vector(CURACAO_TOPO), None)


