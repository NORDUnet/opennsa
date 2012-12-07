import StringIO

from twisted.trial import unittest

from opennsa import nsa
from opennsa.topology import gole

from . import topology as testtopology


TEST_PATH_1 = {
    'source_stp' : nsa.STP('Aruba', 'A2'),
    'dest_stp'   : nsa.STP('Curacao', 'C3'),
    'paths'      :  [ [ nsa.Link('Aruba', 'A2', 'A4'), nsa.Link('Bonaire', 'B1', 'B4'), nsa.Link('Curacao', 'C1', 'C3') ],
                      [ nsa.Link('Aruba', 'A2', 'A1'), nsa.Link('Dominica', 'D4', 'D1'), nsa.Link('Curacao', 'C4', 'C3') ]
                    ]
}

TEST_PATH_2 = {
    'source_stp' : nsa.STP('Aruba', 'A2'),
    'dest_stp'   : nsa.STP('Bonaire', 'B2'),
    'paths'      : [ [ nsa.Link('Aruba', 'A2', 'A4'), nsa.Link('Bonaire', 'B1', 'B2') ],
                     [ nsa.Link('Aruba', 'A2', 'A1'), nsa.Link('Dominica', 'D4', 'D1'), nsa.Link('Curacao', 'C4', 'C1'), nsa.Link('Bonaire', 'B4', 'B2') ] ]
}

# Currently we do not have bandwidth, so this us unused
TEST_PATH_3 = {
    'source_stp': nsa.STP('Aruba', 'A2'),
    'dest_stp'  : nsa.STP('Bonaire', 'B3'),
    'paths'     :  [ [ nsa.Link('Aruba', 'A2', 'A1'), nsa.Link('Dominica', 'D4', 'D1'), nsa.Link('Curacao', 'C4', 'C1'), nsa.Link('Bonaire', 'B4', 'B3') ] ],
    'bandwidth' : 1000
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
        self.topo, _ = gole.parseTopology( [f] )

