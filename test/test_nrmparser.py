import StringIO

from twisted.trial import unittest

from opennsa import nsa, error
from opennsa.topology import nrmparser


NRM_ENTRY = \
"""
# some comment
bi-ethernet     ps              -                               vlan:1780-1788  1000    em0
bi-ethernet     netherlight     netherlight#nordunet-(in|out)   vlan:1780-1783  1000    em1
bi-ethernet     somelight       netherlight#somelight-(in|out)  vlan:1780-1780  1000    "em 8"
bi-ethernet     uvalight        uvalight#uvalight-(in|out)      vlan:1780-1783  1000    em2
"""

# uni-ethernet    test            uvalight:ndn-uvalight           vlan:1780-1783      em2

class NRMParserTest(unittest.TestCase):

    def testNMLNetworkCreation(self):

        network_name = 'dud'
        nsi_agent = nsa.NetworkServiceAgent('dudnsa', 'http://example.org/fake_nsa_url')
        source = StringIO.StringIO(NRM_ENTRY)
        network = nrmparser.parseTopologySpec(source, network_name, nsi_agent)

        self.assertEquals( network.getInterface('ps'),          'em0')
        self.assertEquals( network.getInterface('netherlight'), 'em1')
        self.assertEquals( network.getInterface('somelight'),   'em 8')
        self.assertEquals( network.getInterface('uvalight'),    'em2')

        self.assertRaises( error.TopologyError, network.getInterface, 'na')

        # should test alias as well

