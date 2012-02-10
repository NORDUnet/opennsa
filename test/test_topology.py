import StringIO

from twisted.trial import unittest

from opennsa import nsa, topology

from . import topology as testtopology


STP_A1 = nsa.STP('Aruba', 'A1')
STP_A2 = nsa.STP('Aruba', 'A2')
STP_A3 = nsa.STP('Aruba', 'A3')
STP_A4 = nsa.STP('Aruba', 'A4')

STP_B1 = nsa.STP('Bonaire', 'B1')
STP_B2 = nsa.STP('Bonaire', 'B2')
STP_B3 = nsa.STP('Bonaire', 'B3')
STP_B4 = nsa.STP('Bonaire', 'B4')

STP_C1 = nsa.STP('Curacao', 'C1')
STP_C2 = nsa.STP('Curacao', 'C2')
STP_C3 = nsa.STP('Curacao', 'C3')
STP_C4 = nsa.STP('Curacao', 'C4')

STP_D1 = nsa.STP('Dominica', 'D1')
STP_D2 = nsa.STP('Dominica', 'D2')
STP_D3 = nsa.STP('Dominica', 'D3')
STP_D4 = nsa.STP('Dominica', 'D4')


TEST_PATH_1 = {
    'source_stp' : STP_A2,
    'dest_stp'   : STP_C3,
    'paths'      :  [ [ nsa.Link(STP_A2, STP_A4), nsa.Link(STP_B1, STP_B4), nsa.Link(STP_C1, STP_C3) ],
                      [ nsa.Link(STP_A2, STP_A1), nsa.Link(STP_D4, STP_D1), nsa.Link(STP_C4, STP_C3) ]
                    ]
}

TEST_PATH_2 = {
    'source_stp' : STP_A2,
    'dest_stp'   : STP_B2,
    'paths'      : [ [ nsa.Link(STP_A2, STP_A4), nsa.Link(STP_B1, STP_B2) ],
                     [ nsa.Link(STP_A2, STP_A1), nsa.Link(STP_D4, STP_D1), nsa.Link(STP_C4, STP_C1), nsa.Link(STP_B4, STP_B2) ] ]
}

# Currently we do not have bandwidth, so this us unused
TEST_PATH_3 = {
    'source_stp': STP_A2,
    'dest_stp'  : STP_B3,
    'paths'     :  [ [ nsa.Link(STP_A2, STP_A1), nsa.Link(STP_D4, STP_D1), nsa.Link(STP_C4, STP_C1), nsa.Link(STP_B4, STP_B3) ] ],
    'bandwidth' : nsa.BandwidthParameters(1000, 1000, 1000)
}

TEST_PATHS = [ TEST_PATH_1, TEST_PATH_2 ]



class GenericTopologyTest:

    def testParseAndFindPath(self):

        for tp in TEST_PATHS:

            paths = self.topo.findPaths(tp['source_stp'], tp['dest_stp'], tp.get('bandwidth'))
            for path in paths:
                self.assertIn(path.network_links, tp['paths'])
            self.assertEquals(len(paths), len(tp['paths']))



class GOLETopologyTest(GenericTopologyTest, unittest.TestCase):

    def setUp(self):
        f = StringIO.StringIO(testtopology.TEST_TOPOLOGY)
        self.topo = topology.parseTopology( [f] )

