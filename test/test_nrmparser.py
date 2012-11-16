import StringIO

from twisted.trial import unittest

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

