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

        nrm_ports = nrmparser.parsePortSpec( StringIO.StringIO(NRM_ENTRY) )

        port_map = dict( [ (p.name, p.interface) for p in nrm_ports ] )

        self.assertEquals( port_map.get('ps'),           'em0')
        self.assertEquals( port_map.get('netherlight'),  'em1')
        self.assertEquals( port_map.get('somelight'),    'em8')
        self.assertEquals( port_map.get('uvalight'),     'em2')

        # should test alias as well

