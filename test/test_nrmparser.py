import StringIO

from twisted.trial import unittest

from opennsa import nsa, error
from opennsa.topology import nrmparser


NRM_ENTRY = \
"""
# some comment
bi-ethernet     ps              -                               vlan:1780-1788      em0
bi-ethernet     netherlight     netherlight:ndn-netherlight     vlan:1780-1783      em1
bi-ethernet     somelight       netherlight:ndn-somelight       vlan:1780-1780      "em 8"
bi-ethernet     uvalight        uvalight:ndn-uvalight           vlan:1780-1783      em2
"""


class NRMParserTest(unittest.TestCase):

    def testBasicParsing(self):

        source = StringIO.StringIO(NRM_ENTRY)

        entries = nrmparser.parseTopologySpec(source)

        self.failUnlessEquals(len(entries), 4)

        port_names = [ ne.port_name for ne in entries ]
        self.failUnlessEqual(port_names, [ 'ps', 'netherlight', 'somelight', 'uvalight' ])

        interfaces = [ ne.interface for ne in entries ]
        self.failUnlessEqual(interfaces, [ 'em0', 'em1', 'em 8', 'em2' ])


    def testNMLNetworkCreation(self):

        source = StringIO.StringIO(NRM_ENTRY)

        entries = nrmparser.parseTopologySpec(source)

        network_name = 'dud'
        ns_agent = nsa.NetworkServiceAgent('dudnsa', 'http://example.org/fake_nsa_url')

        network = nrmparser.createNetwork(network_name, ns_agent, entries)

        self.assertEquals( network.getInterface('ps'),          'em0')
        self.assertEquals( network.getInterface('netherlight'), 'em1')
        self.assertEquals( network.getInterface('somelight'),   'em 8')
        self.assertEquals( network.getInterface('uvalight'),    'em2')

        self.assertRaises( error.TopologyError, network.getInterface, 'na')

        # should test alias as well

