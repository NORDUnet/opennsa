"""
OpenNSA Juniper/JunOS VPLS backend.

Intended to match Canaries usage.

Requires a JunOS device with VPLS support (duh)

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2017)

"""

# Configuration conventions / environment, and snippets

# logical unit number normally matches a vlan ID (or a first VLAN number in a list)
#
# interfaces {
#     et-x/y/z {
#         description "ANA-300 link to Amsterdam";
#         flexible-vlan-tagging;
#         encapsulation flexible-ethernet-services;
#         .....
#         unit 1000 {
#             description "13903CS01-NORDUNet-AMST1-NYCN1 [L2VPN circuit Amsterdam to New York for NORDUNet]";
#             encapsulation vlan-vpls;
#             vlan-id-list 1000;
#             family vpls;
#         }
#
#     et-x/y/w {
#         description "CANARIE/ANA-300 link to New York City";
#         flexible-vlan-tagging;
#         encapsulation flexible-ethernet-services;
#         .....
#         unit 1000 {
#             description "13903CS01-NORDUNet-AMST1-NYCN1 [L2VPN circuit Amsterdam to New York for NORDUNet]";
#             encapsulation vlan-vpls;
#             vlan-id-list 1000;
#             family vpls;
#         }
#     }
#
#
# routing-instances {
#     13903CS01-NORDUNet-AMST1-NYCN1 {
#         instance-type vpls;
#         interface et-x/y/z.1000;
#         interface et-x/y/w.1000;
#         route-distinguisher 6509:1390301;
#         vrf-target target:6509:1390301;
#         protocols {
#             vpls {
#                 site-range 2;
#                 no-tunnel-services;
#                 site AMST1 {
#                     site-identifier 1;
#                     interface et-x/y/z.1000;
#                 }
#                 site NYCN1 {
#                     site-identifier 2;
#                     interface et-x/y/w.1000;
#                 }
#             }
#         }
#     }
#


#import random

from twisted.python import log
from twisted.internet import defer, reactor

from opennsa import constants as cnt, config
from opennsa.backends.common import genericbackend, ssh


LOG_SYSTEM = 'JuniperVPLS'


# JunOS commands, static
CONFIGURE   = 'configure private'
COMMIT      = 'commit'

# JunOS commands, parameterized

# Interface unit configuration
#SET_UNIT                = 'set interfaces %(interface) unit %(unit)'
#SET_UNIT_DESCRIPTION    = 'set interfaces %(interface) unit %(unit) description %(description)'
#SET_UNIT_ENCAPSULATION  = 'set interfaces %(interface) unit %(unit) encapsulation vlan-vpls'
#SET_UNIT_VLAN           = 'set interfaces %(interface) unit %(unit) vlan-id-list %(vlan)'
#SET_UNIT_FAMILY         = 'set interfaces %(interface) unit %(unit) family vpls'

SET_UNIT = 'set interfaces {interface} unit {unit} description "{description}" encapsulation vlan-vpls vlan-id {vlan} family vpls'

# Routing instance configuration
#SET_RI                      = 'set routing-instance %(instance)'
SET_RI_INSTANCE_TYPE        = 'set routing-instances {instance} instance-type vpls'
SET_RI_INTERFACE            = 'set routing-instances {instance} interface {interface}'
SET_RI_ROUTE_DISTINGUISHER  = 'set routing-instances {instance} route-distinguisher {route_distinguisher}'
SET_RI_VRF_TARGET           = 'set routing-instances {instance} vrf-target {vrf_target}'
SET_RI_PROTOCOLS            = 'set routing-instances {instance} protocols vpls site-range 2 no-tunnel-services'
SET_RI_VPLS_SITE            = 'set routing-instances {instance} protocols vpls site {site} site-identifier {site_id} interface {interface}'
#SET_RI_VPLS_SITE2           = 'set routing-instances %(instance) protocols vpls site %(site) site-identifier 2 interface %(interface)'

# Delete statements
DELETE_UNIT             = 'delete interfaces {interface} unit {unit}'
DELETE_ROUTING_INSTANCE = 'delete routing-instance {instance}'



def createSetupCommands(source_port, dest_port, vlan, instance_id, description, route_distinguiser, vrf_target):

    source_interface = source_port + '.' + str(vlan)
    dest_interface   = dest_port   + '.' + str(vlan)

    source_unit = SET_UNIT.format(interface=source_port, unit=vlan, description=description, vlan=vlan)
    dest_unit   = SET_UNIT.format(interface=dest_port,   unit=vlan, description=description, vlan=vlan)

    ri_instance   = SET_RI_INSTANCE_TYPE.format(instance=instance_id)
    ri_interface1 = SET_RI_INTERFACE.format(instance=instance_id, interface=source_interface)
    ri_interface2 = SET_RI_INTERFACE.format(instance=instance_id, interface=dest_interface)

    ri_route_dist = SET_RI_ROUTE_DISTINGUISHER.format(instance=instance_id, route_distinguisher=route_distinguiser)
    ri_vrf_target = SET_RI_VRF_TARGET.format(instance=instance_id, vrf_target=vrf_target)

    ri_protocols  = SET_RI_PROTOCOLS.format(instance=instance_id)
    ri_vpls_site1 = SET_RI_VPLS_SITE.format(instance=instance_id, site='MTRL1', site_id='1', interface=source_interface)
    ri_vpls_site2 = SET_RI_VPLS_SITE.format(instance=instance_id, site='MTRL2', site_id='2', interface=dest_interface)

    commands = [ source_unit, dest_unit, ri_instance, ri_interface1, ri_interface2, ri_route_dist, ri_vrf_target, ri_protocols, ri_vpls_site1, ri_vpls_site2 ]

    return commands


def createDeleteCommands(source_port, dest_port, vlan, instance_id):

    delete_source_unit = DELETE_UNIT.format(interface=source_port, unit=vlan)
    delete_dest_unit   = DELETE_UNIT.format(interface=dest_port,   unit=vlan)
    delete_ri          = DELETE_ROUTING_INSTANCE.format(instance=instance_id)

    commands = [ delete_source_unit, delete_dest_unit, delete_ri ]

    return commands


# ---


class SSHChannel(ssh.SSHChannel):

    name = 'session'

    def __init__(self, conn):
        ssh.SSHChannel.__init__(self, conn=conn)

        self.line = ''

        self.wait_defer = None
        self.wait_line  = None


    @defer.inlineCallbacks
    def sendCommands(self, commands):
        LT = '\r' # line termination

        try:
            yield self.conn.sendRequest(self, 'shell', '', wantReply=1)

            d = self.waitForLine('[edit]', 3)
            self.write(CONFIGURE + LT)
            yield d

            log.msg('Entered configure mode', debug=True, system=LOG_SYSTEM)

            for cmd in commands:
                log.msg('CMD> %s' % cmd, system=LOG_SYSTEM)
                d = self.waitForLine('[edit]', 3)
                self.write(cmd + LT)
                yield d

            d = self.waitForLine('commit complete', 20)
            self.write(COMMIT + LT)
            yield d

        except Exception as e:
            log.msg('Error sending commands: %s' % str(e))
            raise e

        log.msg('Commands successfully committed', debug=True, system=LOG_SYSTEM)
        self.sendEOF()
        self.closeIt()


    def waitForLine(self, line, timeout=None):

        self.wait_line = line
        self.wait_defer = defer.Deferred()
        self.delayed_call = None

        if timeout is not None:
            assert type(timeout) in (int, float), 'Timeout must be a number (int or float)'
            self.delayed_call = reactor.callLater(timeout, self.waitTimeout)
        return self.wait_defer


    def waitTimeout(self):
        log.msg('Timeout while waiting for line: ' + self.wait_line, system=LOG_SYSTEM)
        self.wait_line  = None
        wd = self.wait_defer = None
        self.delayed_call = None
        defer.timeout(wd)


    def matchLine(self, line):

        if self.wait_line is None and self.wait_defer is None:
            log.msg('Nothing to wait for line:: ' + line, debug=True, system=LOG_SYSTEM)
            return

        if self.wait_line and self.wait_defer:
            if self.wait_line in line.strip():
                d = self.wait_defer
                self.wait_line  = None
                self.wait_defer = None
                if self.delayed_call is not None:
                    self.delayed_call.cancel()
                    self.delayed_call = None
                d.callback(self)

            else:
                log.msg('Discarding wait line: ' + line, debug=True, system=LOG_SYSTEM)

        else:
            log.msg('Weird wait configuration: ' + str(self.wait_line) + ' / ' + str(self.wait_defer), system=LOG_SYSTEM)
            pass


    def dataReceived(self, data):
        if len(data) == 0:
            pass
        else:
            self.line += data
            if '\n' in data:
                lines = [ line.strip() for line in self.line.split('\n') if line.strip() ]
                self.line = ''
                for l in lines:
                    self.matchLine(l)



class JuniperVPLSCommandSender:


    def __init__(self, host, port, ssh_host_fingerprint, user, ssh_public_key_path, ssh_private_key_path):

        self.ssh_connection_creator = \
             ssh.SSHConnectionCreator(host, port, [ ssh_host_fingerprint ], user, ssh_public_key_path, ssh_private_key_path)

        self.ssh_connection = None # cached connection


    def _getSSHChannel(self):

        def setSSHConnectionCache(ssh_connection):
            log.msg('SSH Connection created and cached', system=LOG_SYSTEM)
            self.ssh_connection = ssh_connection
            return ssh_connection

        def gotSSHConnection(ssh_connection):
            channel = SSHChannel(conn = ssh_connection)
            ssh_connection.openChannel(channel)
            return channel.channel_open

        if self.ssh_connection and not self.ssh_connection.transport.factory.stopped:
            log.msg('Reusing SSH connection', debug=True, system=LOG_SYSTEM)
            return gotSSHConnection(self.ssh_connection)
        else:
            # since creating a new connection should be uncommon, we log it
            # this makes it possible to see if something fucks up and creates connections continuously
            log.msg('Creating new SSH connection', system=LOG_SYSTEM)
            d = self.ssh_connection_creator.getSSHConnection()
            d.addCallback(setSSHConnectionCache)
            d.addCallback(gotSSHConnection)
            return d


    def _sendCommands(self, commands):

        def gotChannel(channel):
            d = channel.sendCommands(commands)
            return d

        d = self._getSSHChannel()
        d.addCallback(gotChannel)
        return d


    def setupLink(self, source_port, dest_port, vlan, instance_id, as_number):

        # createSetupCommands(source_port, dest_port, vlan, instance_id, description, route_distinguiser, vrf_target)

        description = instance_id + ' [ X-connect created by OpenNSA ]'
        unique_id = instance_id[:5] + instance_id[7:9]
        route_distinguisher = as_number + ':' + unique_id
        vrf_target = 'target:' + as_number + ':' + unique_id

        commands = createSetupCommands(source_port, dest_port, vlan, instance_id, description, route_distinguisher, vrf_target)

        return self._sendCommands(commands)


    def teardownLink(self, source_port, dest_port, vlan, instance_id):

        # createDeleteCommands(source_port, dest_port, vlan, instance_id)

        commands = createDeleteCommands(source_port, dest_port, vlan, instance_id)

        return self._sendCommands(commands)


# --------


class JunosUnitTarget(object):

    def __init__(self, port, vlan):
        self.port = port
        self.vlan = vlan

    def __str__(self):
        return '<JunosUnitTarget %s.%i>' % (self.port, self.vlan)



class JuniperVPLSConnectionManager:


    def __init__(self, port_map, host, port, host_fingerprint, user, ssh_public_key, ssh_private_key, as_number):

        self.port_map = port_map
        self.command_sender = JuniperVPLSCommandSender(host, port, host_fingerprint, user, ssh_public_key, ssh_private_key)
        self.as_number = as_number


    def getResource(self, port, label):
        assert label is not None and label.type_ == cnt.ETHERNET_VLAN, 'Label must be vlan'
        device_port = self.port_map[port]
        if device_port is None:
            raise ValueError('Invalid port specified: %s' % device_port)
        return port + '.' + label.labelValue()


    def getTarget(self, port, label):
        assert label is not None and label.type_ == cnt.ETHERNET_VLAN, 'Label must be vlan'
        device_port = self.port_map[port]
        if device_port is None:
            raise ValueError('Invalid port specified: %s' % device_port)

        vlan = int(label.labelValue())
        assert 1 <= vlan <= 4095, 'Invalid label value for vlan: %s' % label.labelValues()

        return JunosUnitTarget(self.port_map[port], vlan)


    def createConnectionId(self, source_target, dest_target):
        raise NotImplementedError('Connection id should be assigned in plugin')


    def canSwapLabel(self, label_type):
        # Not right now, maybe in the future
        return False


    def setupLink(self, connection_id, source_target, dest_target, bandwidth):

        def linkUp(_):
            log.msg('Link %s -> %s setup done' % (source_target, dest_target), system=LOG_SYSTEM)

        assert source_target.vlan == dest_target.vlan, 'Source and destination vlan must match'

        d = self.command_sender.setupLink(source_target.port, dest_target.port, dest_target.vlan, connection_id, self.as_number)
        d.addCallback(linkUp)
        return d


    def teardownLink(self, connection_id, source_target, dest_target, bandwidth):

        def linkDown(_):
            log.msg('Link %s -> %s teardown done' % (source_target, dest_target), system=LOG_SYSTEM)

        assert source_target.vlan == dest_target.vlan, 'Source and destination vlan must match'

        d = self.command_sender.teardownLink(source_target.port, dest_target.port, dest_target.vlan, connection_id)
        d.addCallback(linkDown)
        return d



def JuniperVPLSBackend(network_name, nrm_ports, parent_requester, cfg):

    name = 'JuniperVPLS %s' % network_name
    nrm_map  = dict( [ (p.name, p) for p in nrm_ports ] ) # for the generic backend
    port_map = dict( [ (p.name, p.interface) for p in nrm_ports ] ) # for the nrm backend

    # extract config items
    host             = cfg[config.JUNIPER_HOST]
    port             = cfg.get(config.JUNIPER_PORT, 22)
    host_fingerprint = cfg[config.JUNIPER_HOST_FINGERPRINT]
    user             = cfg[config.JUNIPER_USER]
    ssh_public_key   = cfg[config.JUNIPER_SSH_PUBLIC_KEY]
    ssh_private_key  = cfg[config.JUNIPER_SSH_PRIVATE_KEY]
    as_number        = cfg[config.AS_NUMBER]

    cm = JuniperVPLSConnectionManager(port_map, host, port, host_fingerprint, user, ssh_public_key, ssh_private_key, as_number)
    return genericbackend.GenericBackend(network_name, nrm_map, cm, parent_requester, name)
