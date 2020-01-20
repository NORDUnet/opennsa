from twisted.trial import unittest

from opennsa.topology import linkvector


ARUBA_PORT       = 'aru'
BONAIRE_PORT     = 'bon'
CURACAO_PORT     = 'cur'
DOMINICA_PORT    = 'dom'

LOCAL_TOPO      = 'local:topo'
ARUBA_TOPO      = 'aruba:topo'
BONAIRE_TOPO    = 'bonaire:topo'
CURACAO_TOPO    = 'curacao:topo'
DOMINCA_TOPO    = 'dominica:topo'


class LinkVectorTest(unittest.TestCase):

    def setUp(self):

        self.rv = linkvector.LinkVector( [ LOCAL_TOPO ] )


    def testNoReachability(self):

        self.rv.updateVector(ARUBA_TOPO, ARUBA_PORT, { ARUBA_TOPO : 1, BONAIRE_TOPO : 2 , CURACAO_TOPO : 3 } )
        self.failUnlessEqual(self.rv.vector(ARUBA_TOPO, source=LOCAL_TOPO), (None, None))


    def testPathfindingVectorManualVectors(self):

        self.rv.updateVector(LOCAL_TOPO, ARUBA_PORT,     { ARUBA_TOPO   : 1 } )
        self.rv.updateVector(ARUBA_TOPO, ARUBA_PORT, { ARUBA_TOPO : 1, BONAIRE_TOPO : 2 , CURACAO_TOPO : 3 } )

        self.failUnlessEqual(self.rv.vector(ARUBA_TOPO,   source=LOCAL_TOPO), (LOCAL_TOPO, ARUBA_PORT))
        self.failUnlessEqual(self.rv.vector(BONAIRE_TOPO, source=LOCAL_TOPO), (LOCAL_TOPO, ARUBA_PORT))
        self.failUnlessEqual(self.rv.vector(CURACAO_TOPO, source=LOCAL_TOPO), (LOCAL_TOPO, ARUBA_PORT))

#        self.failUnlessEquals( self.rv.listVectors(), { ARUBA_TOPO   : 1, BONAIRE_TOPO : 2, CURACAO_TOPO : 3 } )

        self.rv.updateVector(BONAIRE_TOPO, BONAIRE_PORT, { BONAIRE_TOPO: 1, CURACAO_TOPO : 2 } )

        self.failUnlessEqual( self.rv.vector(ARUBA_TOPO,   source=LOCAL_TOPO), (LOCAL_TOPO, ARUBA_PORT))
        self.failUnlessEqual( self.rv.vector(BONAIRE_TOPO, source=LOCAL_TOPO), (LOCAL_TOPO, ARUBA_PORT))
        self.failUnlessEqual( self.rv.vector(CURACAO_TOPO, source=LOCAL_TOPO), (LOCAL_TOPO, ARUBA_PORT))

#        self.failUnlessEquals( self.rv.listVectors(), { ARUBA_TOPO   : 1, BONAIRE_TOPO : 1, CURACAO_TOPO : 2 } )


#    def testLocalNetworkExclusion(self):
#
#        # i think this test is bogus now
#        self.rv = linkvector.LinkVector(local_networks=[ BONAIRE_TOPO ])
#
#        self.rv.updateVector(ARUBA_TOPO, ARUBA_PORT, { ARUBA_TOPO : 1, BONAIRE_TOPO : 1, CURACAO_TOPO : 2 } )
#
#        self.failUnlessEqual( self.rv.vector(ARUBA_TOPO,   source=BONAIRE_TOPO), (None, None))
#        self.failUnlessEqual( self.rv.vector(BONAIRE_TOPO, source=BONAIRE_TOPO), (None, None))
#        self.failUnlessEqual( self.rv.vector(CURACAO_TOPO, source=BONAIRE_TOPO), (BONAIRE_TOPO, BONAIRE_PORT))


    def testBlackList(self):

        self.rv = linkvector.LinkVector( [ BONAIRE_TOPO ], blacklist_networks = [ CURACAO_TOPO ] )

        self.rv.updateVector(BONAIRE_TOPO, ARUBA_PORT,   { ARUBA_TOPO   : 1, CURACAO_TOPO : 2 } )
        self.rv.updateVector(BONAIRE_TOPO, CURACAO_PORT, { CURACAO_TOPO : 1 } )

        self.failUnlessEqual( self.rv.vector(ARUBA_TOPO,   source=BONAIRE_TOPO), (BONAIRE_TOPO, ARUBA_PORT))
        self.failUnlessEqual( self.rv.vector(BONAIRE_TOPO, source=BONAIRE_TOPO), (None, None))
        self.failUnlessEqual( self.rv.vector(CURACAO_TOPO, source=BONAIRE_TOPO), (None, None))


    def testMaxCost(self):

        self.rv = linkvector.LinkVector( [ LOCAL_TOPO ], max_cost=3 )

        self.rv.updateVector(LOCAL_TOPO, ARUBA_PORT, { ARUBA_TOPO : 1, BONAIRE_TOPO : 2 , CURACAO_TOPO : 4 } )

        self.failUnlessEqual( self.rv.vector(ARUBA_TOPO,   source=LOCAL_TOPO), (LOCAL_TOPO, ARUBA_PORT))
        self.failUnlessEqual( self.rv.vector(BONAIRE_TOPO, source=LOCAL_TOPO), (LOCAL_TOPO, ARUBA_PORT))
        self.failUnlessEqual( self.rv.vector(CURACAO_TOPO, source=LOCAL_TOPO), (None, None))


    def testUnreachabilityThenReachability(self):

        self.rv = linkvector.LinkVector( [ LOCAL_TOPO ] )

        self.rv.updateVector(LOCAL_TOPO, ARUBA_PORT,     { ARUBA_TOPO   : 1 } )
        self.rv.updateVector(BONAIRE_TOPO, CURACAO_PORT, { CURACAO_TOPO : 1 } )

        self.failUnlessEqual(self.rv.vector(ARUBA_TOPO,   source=LOCAL_TOPO), (LOCAL_TOPO, ARUBA_PORT))
        self.failUnlessEqual(self.rv.vector(BONAIRE_TOPO, source=LOCAL_TOPO), (None, None))
        self.failUnlessEqual(self.rv.vector(CURACAO_TOPO, source=LOCAL_TOPO), (None, None))

        self.rv.updateVector(ARUBA_TOPO, BONAIRE_PORT, { BONAIRE_TOPO : 1 } )

        self.failUnlessEqual(self.rv.vector(CURACAO_TOPO, source=LOCAL_TOPO), (LOCAL_TOPO, ARUBA_PORT))


    def testMultiNetworkReachability(self):

        self.rv = linkvector.LinkVector( [ LOCAL_TOPO ] )

        self.rv.updateVector(LOCAL_TOPO, ARUBA_PORT,   { ARUBA_TOPO : 1 } )
        self.rv.updateVector(ARUBA_TOPO, BONAIRE_PORT, { BONAIRE_TOPO : 1 } )

        self.failUnlessEqual(self.rv.vector(ARUBA_TOPO,   source=LOCAL_TOPO), (LOCAL_TOPO, ARUBA_PORT))
        self.failUnlessEqual(self.rv.vector(BONAIRE_TOPO, source=LOCAL_TOPO), (LOCAL_TOPO, ARUBA_PORT))
        self.failUnlessEqual(self.rv.vector(CURACAO_TOPO, source=LOCAL_TOPO), (None, None))

        self.rv.updateVector(BONAIRE_TOPO, CURACAO_PORT, { CURACAO_TOPO : 1 } )

        self.failUnlessEqual(self.rv.vector(CURACAO_TOPO, source=LOCAL_TOPO), (LOCAL_TOPO, ARUBA_PORT))


    def testLocalThenRemoteVector(self):

        ARUBA_OJS_NET   = 'aruba:ojs'
        ARUBA_SAN_NET   = 'aruba:san'

        self.rv = linkvector.LinkVector( [ ARUBA_OJS_NET, ARUBA_SAN_NET ] )

        self.failUnlessEqual(self.rv.vector(ARUBA_OJS_NET, source=ARUBA_SAN_NET), (None, None))
        self.failUnlessEqual(self.rv.vector(ARUBA_SAN_NET, source=ARUBA_OJS_NET), (None, None))

        self.rv.updateVector(ARUBA_OJS_NET, 'san', { ARUBA_SAN_NET: 1 } )
        self.rv.updateVector(ARUBA_SAN_NET, 'ojs', { ARUBA_OJS_NET: 1 } )
        self.rv.updateVector(ARUBA_SAN_NET, 'bon', { BONAIRE_TOPO: 1 } )

        self.failUnlessEqual(self.rv.vector(ARUBA_OJS_NET, source=ARUBA_SAN_NET), (ARUBA_SAN_NET, 'ojs'))
        self.failUnlessEqual(self.rv.vector(ARUBA_SAN_NET, source=ARUBA_OJS_NET), (ARUBA_OJS_NET, 'san'))

        self.failUnlessEqual(self.rv.vector(BONAIRE_TOPO,  source=ARUBA_OJS_NET), (ARUBA_OJS_NET, 'san'))
        self.failUnlessEqual(self.rv.vector(BONAIRE_TOPO,  source=ARUBA_SAN_NET), (ARUBA_SAN_NET, 'bon'))

