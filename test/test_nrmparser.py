import StringIO

from twisted.trial import unittest

from opennsa.topology import nrm


NRM_ENTRY = \
"""
# some comment
ethernet     ps              -                               vlan:1780-1788  1000    em0     -
ethernet     netherlight     netherlight#nordunet-(in|out)   vlan:1780-1783  1000    em1     -
ethernet     somelight       somelight#somelight-(in|out)    vlan:1780-1780  1000    em8     -
ethernet     uvalight        uvalight#intf-(in|out)          vlan:1780-1783  1000    em2     -
ethernet     splight         splight#intf-(in|out)           mpls:1780-1783  1000    em7     -
"""


class NRMParserTest(unittest.TestCase):

    def testPortMapping(self):

        nrm_ports = nrm.parsePortSpec( StringIO.StringIO(NRM_ENTRY) )

        port_map = dict( [ (p.name, p.interface) for p in nrm_ports ] )

        self.assertEquals( port_map.get('ps'),           'em0')
        self.assertEquals( port_map.get('netherlight'),  'em1')
        self.assertEquals( port_map.get('somelight'),    'em8')
        self.assertEquals( port_map.get('uvalight'),     'em2')
        self.assertEquals( port_map.get('splight'),      'em7')

        # should test alias as well

