"""
Brocade backend.
Contributed by Balasubramania Pillai from MAX Gigapop.
Ported to OpenNSA NSIv2 by Henrik Thostrup Jensen (summer 2013)
Further contributions/fixes from Jeronimo Aguiar from AMPATH.

Notes:

configure terminal
vlan $vlan_id name $name
tagged $source_port
tagged $dest_port
end

Teardown:

configure terminal
no vlan $vlan_id
end
"""

import string
import random

from twisted.python import log
from twisted.internet import defer

from opennsa import constants as cnt, config
from opennsa.backends.common import ssh, genericbackend

LOG_SYSTEM = 'opennsa.brocade'


COMMAND_PRIVILEGE   = 'enable %s'
COMMAND_CONFIGURE   = 'configure terminal'
COMMAND_END         = 'end'

COMMAND_VLAN        = 'vlan %(vlan)i name %(name)s'
#COMMAND_TAGGED      = 'tagged %(port)s'
COMMAND_TAGGED      = 'tagged ethernet %(port)s'

COMMAND_NO_VLAN     = 'no vlan %(vlan)i'


def _portToInterfaceVLAN(nrm_port):

    port, vlan = nrm_port.split('.')
    vlan = int(vlan)
    return port, vlan


def _createSetupCommands(source_nrm_port, dest_nrm_port):

    log.msg('_createSetupCommands: src %s dst %s' % (source_nrm_port, dest_nrm_port))

    s_port, s_vlan = _portToInterfaceVLAN(source_nrm_port)
    d_port, d_vlan = _portToInterfaceVLAN(dest_nrm_port)

    assert s_vlan == d_vlan, 'Source and destination VLANs differ, unpossible!'

    log.msg('_createSetupCommands: src %s %s dst %s %s' % (s_port, s_vlan, d_port, d_vlan))

    name = 'opennsa-%i' % s_vlan

    cmd_vlan    = COMMAND_VLAN      % { 'vlan' : s_vlan, 'name' : name }
    cmd_s_intf  = COMMAND_TAGGED    % { 'port' : s_port }
    cmd_d_intf  = COMMAND_TAGGED    % { 'port' : d_port }

    commands = [ cmd_vlan, cmd_s_intf, cmd_d_intf ]

    log.msg('_createSetupCommands: commands %s' % (commands))
    return commands


def _createTeardownCommands(source_nrm_port, dest_nrm_port):

    s_port, s_vlan = _portToInterfaceVLAN(source_nrm_port)
    d_port, d_vlan = _portToInterfaceVLAN(dest_nrm_port)

    assert s_vlan == d_vlan, 'Source and destination VLANs differ, unpossible!'

    cmd_no_intf = COMMAND_NO_VLAN % { 'vlan' : s_vlan }

    commands = [ cmd_no_intf ]
    return commands



class SSHChannel(ssh.SSHChannel):

    name = 'session'

    def __init__(self, conn):
        ssh.SSHChannel.__init__(self, conn=conn)

        self.data = ''

        self.wait_defer = None
        self.wait_data  = None


    @defer.inlineCallbacks
    def sendCommands(self, commands, enable_password):
        LT = '\r' # line termination

        try:
            log.msg('Requesting shell for sending commands', debug=True, system=LOG_SYSTEM)
            yield self.conn.sendRequest(self, 'shell', '', wantReply=1)

            d = self.waitForData('>')
            self.write(COMMAND_PRIVILEGE % enable_password + LT)
            yield d
            log.msg('Entered privileged mode', debug=True, system=LOG_SYSTEM)

            d = self.waitForData('#')
            self.write(COMMAND_CONFIGURE + LT)
            yield d
            log.msg('Entered configure mode', debug=True, system=LOG_SYSTEM)

            for cmd in commands:
                log.msg('CMD> %s' % cmd, debug=True, system=LOG_SYSTEM)
                d = self.waitForData('#')
                self.write(cmd + LT)
                yield d

            # not quite sure how to handle failure here
            log.msg('Commands send, sending end command.', debug=True, system=LOG_SYSTEM)
            d = self.waitForData('#')
            self.write(COMMAND_END + LT)
            yield d

        except Exception as e:
            log.msg('Error sending commands: %s' % str(e))
            raise e

        log.msg('Commands successfully send', debug=True, system=LOG_SYSTEM)
        self.sendEOF()
        self.closeIt()


    def waitForData(self, data):
        self.wait_data  = data
        self.wait_defer = defer.Deferred()
        return self.wait_defer


    def dataReceived(self, data):
        if len(data) == 0:
            pass
        else:
            self.data += data
            if self.wait_data and self.wait_data in self.data:
                d = self.wait_defer
                self.data       = ''
                self.wait_data  = None
                self.wait_defer = None
                d.callback(self)




class BrocadeCommandSender:

    def __init__(self, host, port, ssh_host_fingerprint, user, ssh_public_key_path, ssh_private_key_path, enable_password):

        self.ssh_connection_creator = \
             ssh.SSHConnectionCreator(host, port, [ ssh_host_fingerprint ], user, ssh_public_key_path, ssh_private_key_path)
        self.enable_password = enable_password


    @defer.inlineCallbacks
    def sendCommands(self, commands):

        # Open a connection for each request
        # This is done due to the code being based on the Force10 backend
        # It is currently unknown if the Brocade SSH implementation
        # supports multiple ssh channels.

        log.msg('Creating new SSH connection', debug=True, system=LOG_SYSTEM)
        ssh_connection = yield self.ssh_connection_creator.getSSHConnection()

        try:
            channel = SSHChannel(conn=ssh_connection)
            ssh_connection.openChannel(channel)

            yield channel.channel_open
            yield channel.sendCommands(commands, self.enable_password)

        finally:
            ssh_connection.transport.loseConnection()



class BrocadeConnectionManager:

    def __init__(self, log_system, port_map, cfg):
        self.log_system = log_system
        self.port_map   = port_map

        host             = cfg[config.BROCADE_HOST]
        port             = cfg.get(config.BROCADE_PORT, 22)
        host_fingerprint = cfg[config.BROCADE_HOST_FINGERPRINT]
        user             = cfg[config.BROCADE_USER]
        ssh_public_key   = cfg[config.BROCADE_SSH_PUBLIC_KEY]
        ssh_private_key  = cfg[config.BROCADE_SSH_PRIVATE_KEY]
        enable_password  = cfg[config.BROCADE_ENABLE_PASSWORD]

        self.command_sender = BrocadeCommandSender(host, port, host_fingerprint, user, ssh_public_key, ssh_private_key, enable_password)


    def getResource(self, port, label):
        assert label is not None and label.type_ == cnt.ETHERNET_VLAN, 'Label type must be ethernet-vlan'
        return str(label.labelValue())


    def getTarget(self, port, label):
        assert label is not None and label.type_ == cnt.ETHERNET_VLAN, 'Label type must be ethernet-vlan'
        return self.port_map[port] + '.' + label.labelValue()


    def createConnectionId(self, source_target, dest_target):
        return 'B-' + ''.join( [ random.choice(string.hexdigits[:16]) for _ in range(10) ] )


    def canSwapLabel(self, label_type):
        return False


    def setupLink(self, connection_id, source_target, dest_target, bandwidth):

        def linkUp(pt):
            log.msg('Link %s -> %s up' % (source_target, dest_target), system=self.log_system)
            return pt

        commands = _createSetupCommands(source_target, dest_target)
        d = self.command_sender.sendCommands(commands)
        d.addCallback(linkUp)
        return d


    def teardownLink(self, connection_id, source_target, dest_target, bandwidth):

        def linkDown(pt):
            log.msg('Link %s -> %s down' % (source_target, dest_target), system=self.log_system)
            return pt

        commands = _createTeardownCommands(source_target, dest_target)
        d = self.command_sender.sendCommands(commands)
        d.addCallback(linkDown)
        return d



def BrocadeBackend(network_name, nrm_ports, parent_requester, configuration):

    name = 'Brocade %s' % network_name

    nrm_map  = dict( [ (p.name, p) for p in nrm_ports ] ) # for the generic backend
    port_map = dict( [ (p.name, p.interface) for p in nrm_ports ] ) # for the nrm backend

    cm = BrocadeConnectionManager(name, port_map, configuration)
    return genericbackend.GenericBackend(network_name, nrm_map, cm, parent_requester, name)

