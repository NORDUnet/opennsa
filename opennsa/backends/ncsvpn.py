"""
Backend for NCS VPN module.

Author: Henrik Thostrup Jensen <htj at nordu.net>
Copyright: NORDUnet(2011-2013)
"""

import base64

from twisted.python import log

from opennsa import config
from opennsa.backends.common import simplebackend
from opennsa.protocols.shared import httpclient
from opennsa.topology import nml


# basic payload
#
#<service xmlns="http://tail-f.com/ns/ncs" >
#  <object-id>nsi-vpn</object-id>
#  <type>
#    <vpn xmlns="http://nordu.net/ns/ncs/vpn">
#      <side-a>
#        <router>routerA</router>
#        <interface>interface1</interface>
#      </side-a>
#      <side-b>
#        <router></router>
#        <interface>ge-1/0/1</interface>
#      </side-b>
#      <encapsulation-type>ethernet-vlan</encapsulation-type>
#      <vlan>1720</vlan>
#    </vpn>
#  </type>
#</service>
#
# encapsulation type can be ethernet or ethernet-vlan
# vlan must be specified if encapsulation-type is ethernet-vlan, otherwise not
#
# the payload must be posted to the services url, e.g.,:
# http://localhost:8080/api/running/services
#
# To tear down the VPN, do a DELETE against
# "http://localhost:8080/api/running/services/service/nsi-vpn"
#
# The connection id -> object-id mapping is hence rather important to remember, but it can be the


ETHERNET_VPN_PAYLOAD_BASE = """
<service xmlns="http://tail-f.com/ns/ncs" >
  <object-id>%(service_name)s</object-id>
  <type>
    <vpn xmlns="http://nordu.net/ns/ncs/vpn">
      <side-a>
        <router>%(router_a)s</router>
        <interface>%(interface_a)s</interface>
      </side-a>
      <side-b>
        <router>%(router_b)s</router>
        <interface>%(interface_b)s</interface>
      </side-b>
      <encapsulation-type>ethernet</encapsulation-type>
    </vpn>
  </type>
</service>
"""

ETHERNET_VLAN_VPN_PAYLOAD_BASE = """
<service xmlns="http://tail-f.com/ns/ncs" >
  <object-id>%(service_name)s</object-id>
  <type>
    <vpn xmlns="http://nordu.net/ns/ncs/vpn">
      <side-a>
        <router>%(router_a)s</router>
        <interface>%(interface_a)s</interface>
      </side-a>
      <side-b>
        <router>%(router_b)s</router>
        <interface>%(interface_b)s</interface>
      </side-b>
      <encapsulation-type>ethernet-vlan</encapsulation-type>
      <vlan>%(vlan)i</vlan>
    </vpn>
  </type>
</service>
"""



LOG_SYSTEM = 'opennsa.ncsvpn'



class NCSVPNTarget(object):

    def __init__(self, router, interface, vlan=None):
        self.router = router
        self.interface = interface
        self.vlan = vlan

    def __str__(self):
        if self.vlan:
            return '<NCSVPNTarget %s/%s#%i>' % (self.router, self.interface, self.vlan)
        else:
            return '<NCSVPNTarget %s/%s>' % (self.router, self.interface)



def createVPNPayload(service_name, source_target, dest_target):

    intps = {
        'service_name'  : service_name,
        'router_a'      : source_target.router,
        'interface_a'   : source_target.interface,
        'router_b'      : dest_target.router,
        'interface_b'   : dest_target.interface
    }

    if source_target.vlan and dest_target.vlan:
        assert source_target.vlan == dest_target.vlan, 'VLANs must match (until we get rewrite in place)'
        intps['vlan'] = source_target.vlan
        payload = ETHERNET_VLAN_VPN_PAYLOAD_BASE % intps
    else:
        payload = ETHERNET_VPN_PAYLOAD_BASE % intps

    return payload



class NCSVPNConnectionManager:

    def __init__(self, ncs_services_url, user, password, log_system):
        self.ncs_services_url = ncs_services_url
        self.user             = user
        self.password         = password
        self.log_system       = log_system


    def getResource(self, port, label_type, label_value):
        assert label_type in (None, nml.ETHERNET_VLAN), 'Label must be None or VLAN'
        return port # this contains router and port


    def getTarget(self, port, label_type, label_value):
        assert label_type in (None, nml.ETHERNET_VLAN), 'Label must be None or VLAN'
        if label_type == nml.ETHERNET_VLAN:
            assert type(label_value) is int and 1 <= label_value <= 4095, 'Invalid label value for vlan: %s' % label_value

        router, interface = port.split(':')
        return NCSVPNTarget(router, interface, label_value)


    def canSwapLabel(self, label_type):
        return False
        #return label_type == nml.ETHERNET_VLAN:


    def _createAuthzHeader(self):
        return 'Basic ' + base64.b64encode( self.user + ':' + self.password)


    def _createHeaders(self):
        headers = {}
        headers['Content-Type'] = 'text/xml; charset=utf-8'
        headers['Authorization'] = self._createAuthzHeader()
        return headers

    def setupLink(self, connection_id, source_target, dest_target, bandwidth):
        payload = createVPNPayload(connection_id, source_target, dest_target)
        headers = self._createHeaders()

        def linkUp(_):
            log.msg('Link %s -> %s up' % (source_target, dest_target), system=self.log_system)

        d = httpclient.httpRequest(self.ncs_services_url, payload, headers, method='POST')
        d.addCallback(linkUp)
        return d


    def teardownLink(self, connection_id, source_target, dest_target, bandwidth):
        service_url = self.ncs_services_url + '/' + connection_id
        headers = self._createHeaders()

        def linkDown(_):
            log.msg('Link %s -> %s down' % (source_target, dest_target), system=self.log_system)

        d = httpclient.httpRequest(service_url, None, headers, method='DELETE')
        return d
        #log.msg('Link %s -> %s down' % (source_port, dest_port), system=self.log_system)


# --


class NCSVPNBackend(simplebackend.SimpleBackend):

    def __init__(self, network_name, service_registry, parent_system, configuration):

        name = 'NCS VPN (%s)' % network_name

        # extract config items
        cfg_dict = dict(configuration)

        ncs_services_url = cfg_dict[config.NCS_SERVICES_URL]
        user             = cfg_dict[config.NCS_USER]
        password         = cfg_dict[config.NCS_PASSWORD]

        cm = NCSVPNConnectionManager(ncs_services_url, user, password)
        simplebackend.SimpleBackend.__init__(self, network_name, cm, service_registry, parent_system, name)

