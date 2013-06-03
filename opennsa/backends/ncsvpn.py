"""
Backend for NCS VPN module.

Author: Henrik Thostrup Jensen <htj at nordu.net>
Copyright: NORDUnet(2011-2013)
"""

import base64
import hashlib
#import random

from twisted.python import log

from opennsa import config
from opennsa.backends.common import simplebackend, calendar
from opennsa.protocols.shared import httpclient

#from opennsa.topology import nml


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


#    def getResource(self, port, label_type, label_value):
#        assert label_type in (None, nml.ETHERNET_VLAN), 'Label must be None or VLAN'
#        return port # this contains router and port
#

    def getTarget(self, port, vlan):
        #assert label_type in (None, nml.ETHERNET_VLAN), 'Label must be None or VLAN'
#        if label_type == nml.ETHERNET_VLAN:
#            vlan = int(label_value)
#            assert 1 <= vlan <= 4095, 'Invalid label value for vlan: %s' % label_value

        router, interface = port.split(':')
        return NCSVPNTarget(router, interface, vlan)


#    def createConnectionId(self, source_target, dest_target):
#        return 'ON-' + str(random.randint(100000,999999))
#
#
#    def canSwapLabel(self, label_type):
#        return False
#        #return label_type == nml.ETHERNET_VLAN:


    def _createAuthzHeader(self):
        return 'Basic ' + base64.b64encode( self.user + ':' + self.password)


    def _createHeaders(self):
        headers = {}
        headers['Content-Type'] = 'application/vnd.yang.data+xml'
        headers['Authorization'] = self._createAuthzHeader()
        return headers

    def setupLink(self, source_nrm_port, dest_nrm_port):
        # since we don't get a connection id we construct it
        connection_id = 'ON-' + hashlib.sha1(source_nrm_port + '%' + dest_nrm_port).hexdigest()[:10]
        print "NCS VPN CONN ID", connection_id

        sp, s_vlan = source_nrm_port.split('#')
        dp, d_vlan =   dest_nrm_port.split('#')
        source_target = self.getTarget(sp, s_vlan)
        dest_target   = self.getTarget(dp, d_vlan)

        payload = createVPNPayload(connection_id, source_target, dest_target)
        headers = self._createHeaders()

        def linkUp(_):
            log.msg('Link %s -> %s up' % (source_target, dest_target), system=self.log_system)

        d = httpclient.httpRequest(self.ncs_services_url, payload, headers, method='POST')
        d.addCallback(linkUp)
        return d


    def teardownLink(self, source_nrm_port, dest_nrm_port):
        # since we don't get a connection id we construct it
        connection_id = 'ON-' + hashlib.sha1(source_nrm_port + '%' + dest_nrm_port).hexdigest()[:10]
        print "NCS VPN CONN ID", connection_id

        sp, s_vlan = source_nrm_port.split('#')
        dp, d_vlan =   dest_nrm_port.split('#')
        source_target = self.getTarget(sp, s_vlan)
        dest_target   = self.getTarget(dp, d_vlan)

        service_url = self.ncs_services_url + '/service/' + connection_id
        headers = self._createHeaders()

        def linkDown(_):
            log.msg('Link %s -> %s down' % (source_target, dest_target), system=self.log_system)

        d = httpclient.httpRequest(service_url, None, headers, method='DELETE')
        d.addCallback(linkDown)
        return d


# --


class NCSVPNBackend:

    def __init__(self, network_name, configuration):

        self.name = 'NCS VPN (%s)' % network_name

        # extract config items
        cfg_dict = dict(configuration)

        ncs_services_url = str(cfg_dict[config.NCS_SERVICES_URL])
        user             = cfg_dict[config.NCS_USER]
        password         = cfg_dict[config.NCS_PASSWORD]

        self.cm = NCSVPNConnectionManager(ncs_services_url, user, password, self.name)

        self.calendar = calendar.ReservationCalendar()


    def createConnection(self, source_nrm_port, dest_nrm_port, service_parameters):

        source_resource = source_nrm_port.split(':')[0]
        dest_resource   = dest_nrm_port.split(':')[0]

        self.calendar.checkReservation(source_resource, service_parameters.start_time, service_parameters.end_time)
        self.calendar.checkReservation(dest_resource  , service_parameters.start_time, service_parameters.end_time)

        self.calendar.addConnection(source_resource, service_parameters.start_time, service_parameters.end_time)
        self.calendar.addConnection(dest_resource  , service_parameters.start_time, service_parameters.end_time)

        c = simplebackend.GenericConnection(source_nrm_port, dest_nrm_port, service_parameters, self.network_name, self.calendar, self.name, LOG_SYSTEM, self.cm)
        return c

