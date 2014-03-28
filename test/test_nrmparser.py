import StringIO

from twisted.trial import unittest

from opennsa.topology import nrmparser


NRM_ENTRY = \
"""
# some comment
ethernet     ps              -                               vlan:1780-1788  1000    em0     -
ethernet     netherlight     netherlight#nordunet-(in|out)   vlan:1780-1783  1000    em1     -
ethernet     somelight       netherlight#somelight-(in|out)  vlan:1780-1780  1000    em8     -
ethernet     uvalight        uvalight#uvalight-(in|out)      vlan:1780-1783  1000    em2     -
"""


class NRMParserTest(unittest.TestCase):

    def testPortMapping(self):

        network_name = 'dud'
        source = StringIO.StringIO(NRM_ENTRY)
        nml_network, pim = nrmparser.parseTopologySpec(source, network_name)

        self.assertEquals( pim.get('ps'),           'em0')
        self.assertEquals( pim.get('netherlight'),  'em1')
        self.assertEquals( pim.get('somelight'),    'em8')
        self.assertEquals( pim.get('uvalight'),     'em2')

        # should test alias as well

