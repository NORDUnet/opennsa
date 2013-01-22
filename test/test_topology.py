from StringIO import StringIO

from twisted.trial import unittest

from opennsa import nsa
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

ARUBA_PS   = nsa.STP('aruba',   'ps', nsa.BIDIRECTIONAL, [LABEL])
BONAIRE_PS = nsa.STP('bonaire', 'ps', nsa.BIDIRECTIONAL, [LABEL])
CURACAO_PS = nsa.STP('curacao', 'ps', nsa.BIDIRECTIONAL, [LABEL])


class TopologyTest(unittest.TestCase):

    def setUp(self):
        an = nrmparser.parseTopologySpec(StringIO(ARUBA_TOPOLOGY),    'aruba', None)
        bn = nrmparser.parseTopologySpec(StringIO(BONAIRE_TOPOLOGY),  'bonaire', None)
        cn = nrmparser.parseTopologySpec(StringIO(CURACAO_TOPOLOGY),  'curacao', None)
        dn = nrmparser.parseTopologySpec(StringIO(DOMINICA_TOPOLOGY), 'dominica', None)

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

