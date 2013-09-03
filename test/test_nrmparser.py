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
        source = StringIO.StringIO(NRM_ENTRY)
        network, pim = nrmparser.parseTopologySpec(source, network_name, nsa.NetworkServiceAgent('dud:nsa', 'dud_endpoint'))

        self.assertEquals( pim.get('ps'),           'em0')
        self.assertEquals( pim.get('netherlight'),  'em1')
        self.assertEquals( pim.get('somelight'),    'em 8')
        self.assertEquals( pim.get('uvalight'),     'em2')

        # should test alias as well

