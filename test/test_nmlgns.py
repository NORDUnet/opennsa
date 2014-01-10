from twisted.trial import unittest

from opennsa import nsa, error, constants as cnt
from opennsa.topology import nmlgns


ARUBA_NSA       = 'aruba:nsa'
BONAIRE_NSA     = 'bonaire:nsa'
CURACAO_NSA     = 'curacao:nsa'
DOMINICA_NSA    = 'dominica:nsa'

ARUBA_TOPO      = 'aruba:topo'
BONAIRE_TOPO    = 'bonaire:topo'
CURACAO_TOPO    = 'curacao:topo'
DOMINCA_TOPO    = 'dominica:topo'


class NMLGNSTest(unittest.TestCase):

    def setUp(self):

        self.rv = nmlgns.RouteVectors()


    def testBasicPathfindingVector(self):

        vec1 = { BONAIRE_TOPO : 1 , CURACAO_TOPO : 2 }
        self.rv.updateVector(ARUBA_NSA, 1, [ ARUBA_TOPO ], vec1)

        self.failUnlessEqual( self.rv.vector(ARUBA_TOPO),   ARUBA_NSA)
        self.failUnlessEqual( self.rv.vector(BONAIRE_TOPO), ARUBA_NSA)
        self.failUnlessEqual( self.rv.vector(CURACAO_TOPO), ARUBA_NSA)

        vec2 = { CURACAO_TOPO : 1 }
        self.rv.updateVector(BONAIRE_NSA, 1, [ BONAIRE_TOPO ], vec1)

        self.failUnlessEqual( self.rv.vector(ARUBA_TOPO),   ARUBA_NSA)
        self.failUnlessEqual( self.rv.vector(BONAIRE_TOPO), BONAIRE_NSA)
        self.failUnlessEqual( self.rv.vector(CURACAO_TOPO), BONAIRE_NSA)

