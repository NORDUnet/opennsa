from io import StringIO

from twisted.trial import unittest

from opennsa.topology import nrm


NRM_ENTRY = \
"""
# some comment
ethernet     ps              -                              vlan:1780-1788  1000    em0     -
ethernet     eth             -                              -               1000    em0     -
ethernet     netherlight     netherlight#intf1(-in|-out)    vlan:1780-1783  1000    em1     -
ethernet     somelight       somelight#intf2(-in|-out)      vlan:1780-1780  1000    em8     -
ethernet     uvalight        uvalight#intf3(-in|-out)       vlan:1780-1783  1000    em2     -
ethernet     splight         splight#intf4(-in|-out)        mpls:1780-1783  1000    em7     -
ethernet     aruba           aruba.net#intf5(-in|-out)      mpls:1780-1783  1000    em8     -
ethernet     san             aruba.net:san#arb(-in|-out)    vlan:1780-1799  1000    em9     -
"""


class NRMParserTest(unittest.TestCase):

    def testPortMapping(self):

        nrm_ports = nrm.parsePortSpec( StringIO(NRM_ENTRY) )

        port_map = dict( [ (p.name, p.interface) for p in nrm_ports ] )

        self.assertEquals( port_map.get('ps'),           'em0')
        self.assertEquals( port_map.get('netherlight'),  'em1')
        self.assertEquals( port_map.get('somelight'),    'em8')
        self.assertEquals( port_map.get('uvalight'),     'em2')
        self.assertEquals( port_map.get('splight'),      'em7')


    def testRemotePort(self):

        nrm_ports = nrm.parsePortSpec( StringIO(NRM_ENTRY) )

        port_map = dict( [ (p.name, (p.remote_network, p.remote_port)) for p in nrm_ports ] )

        self.assertEquals( port_map.get('ps'),          (None, None) )
        self.assertEquals( port_map.get('netherlight'), ('netherlight', 'intf1'))
        self.assertEquals( port_map.get('somelight'),   ('somelight', 'intf2'))
        self.assertEquals( port_map.get('uvalight'),    ('uvalight', 'intf3'))
        self.assertEquals( port_map.get('aruba'),       ('aruba.net', 'intf5'))
        self.assertEquals( port_map.get('san'),         ('aruba.net:san', 'arb'))

