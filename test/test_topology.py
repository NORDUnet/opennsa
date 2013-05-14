from StringIO import StringIO

from twisted.trial import unittest

from opennsa import nsa, error
from opennsa.topology import nml, nrmparser

# Ring topology

ARUBA_TOPOLOGY = """
bi-ethernet     ps          -                           vlan:1780-1789  1000    em0
bi-ethernet     boniare     bonaire#aruba-(in|out)      vlan:1780-1789  1000    em1
bi-ethernet     dominica    dominica#aruba-(in|out)     vlan:1780-1789   500    em2
"""

BONAIRE_TOPOLOGY = """
bi-ethernet     ps          -                           vlan:1780-1789  1000    em0
bi-ethernet     aruba       aruba#bonaire-(in|out)      vlan:1780-1789  1000    em1
bi-ethernet     curacao     curacao#bonaire-(in|out)    vlan:1780-1789  1000    em2
bi-ethernet     dominica    dominica#bonaire-(in|out)   vlan:1780-1789   100    em3
"""

CURACAO_TOPOLOGY = """
bi-ethernet     ps          -                           vlan:1780-1789  1000    em0
bi-ethernet     boniare     bonaire#curacao-(in|out)    vlan:1780-1789  1000    em1
bi-ethernet     dominica    dominica#curacao-(in|out)   vlan:1780-1789  1000    em2
"""

DOMINICA_TOPOLOGY = """
bi-ethernet     ps          -                           vlan:1780-1789  1000    em0
bi-ethernet     aruba       aruba#dominica-(in|out)     vlan:1780-1789  500     em1
bi-ethernet     bonaire     bonaire#dominica-(in|out)   vlan:1780-1789  100     em2
bi-ethernet     curaco      curacao#dominica-(in|out)   vlan:1780-1789  1000    em3
"""


LABEL = nsa.Label(nml.ETHERNET_VLAN, '1780-1789')

ARUBA_PS   = nsa.STP('aruba',   'ps', nsa.INGRESS, [LABEL])
BONAIRE_PS = nsa.STP('bonaire', 'ps', nsa.INGRESS, [LABEL])
CURACAO_PS = nsa.STP('curacao', 'ps', nsa.INGRESS, [LABEL])


class TopologyTest(unittest.TestCase):

    def setUp(self):
        an,_ = nrmparser.parseTopologySpec(StringIO(ARUBA_TOPOLOGY),    'aruba',    nsa.NetworkServiceAgent('aruba',    'a-endpoint'))
        bn,_ = nrmparser.parseTopologySpec(StringIO(BONAIRE_TOPOLOGY),  'bonaire',  nsa.NetworkServiceAgent('bonaire',  'b-endpoint'))
        cn,_ = nrmparser.parseTopologySpec(StringIO(CURACAO_TOPOLOGY),  'curacao',  nsa.NetworkServiceAgent('curacao',  'c-endpoint'))
        dn,_ = nrmparser.parseTopologySpec(StringIO(DOMINICA_TOPOLOGY), 'dominica', nsa.NetworkServiceAgent('dominica', 'd-endpoint'))

        self.topology = nml.Topology()
        for n in [ an, bn, cn, dn ]:
            self.topology.addNetwork(n)


    def testPathfinding(self):

        paths = self.topology.findPaths(ARUBA_PS, BONAIRE_PS, 100)
#        for p in paths:
#            print "P", p
        self.assertEquals(len(paths), 3)

        lengths = [ len(path) for path in paths ]
        self.assertEquals(lengths, [2,3,4])
        # to lazy to do structural tests


        # test bandwidth
        paths = self.topology.findPaths(ARUBA_PS, BONAIRE_PS, 300)
        self.assertEquals(len(paths), 2)

        paths = self.topology.findPaths(ARUBA_PS, BONAIRE_PS, 800)
        self.assertEquals(len(paths), 1)


    def testNoAvailableBandwidth(self):
        self.failUnlessRaises(error.BandwidthUnavailableError, self.topology.findPaths, ARUBA_PS, BONAIRE_PS, 1200)

