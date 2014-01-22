"""
Force10 Backend.

This backend will only work with SSH version 2 capable Force10 switches.

This excludes most, if not all, of the etherscale series.

The backend has been developed for the E series.
The backend has been developed and tested on a Terascale E300 switch.

The switch (or router, depending on your level off pedanticness) is configured
by the backend logging via ssh, requesting a cli, and firing the necessary
command for configuring a VLAN. This approach was choosen over netconf / XML,
as a fairly reliable source said that not all the necessary functionality
needed was available via the previously mentioned interfaces.

Currently the backend does support VLAN rewriting, and I am not sure if/how it
is supported.

Configuration:

To setup a VLAN connection:

configure
interface vlan $vlan_id
name $name
description $description
no shut
tagged $source_port
tagged $dest_port
end

Teardown:

configure
no interface vlan $vlan_id
end

Ensure that the interfaces are configure to be layer 2.

Ralph developed a backend for etherscale, where a lot of the input from this
backend comes from.

Authors: Henrik Thostrup Jensen <htj@nordu.net>
         Ralph Koning <R.Koning@uva.nl>

Copyright: NORDUnet (2011-2013)
"""

import string
import random
import os

from twisted.python import log
from twisted.internet import defer
from twisted.conch.ssh import session

from opennsa import constants as cnt, config
from opennsa.backends.common import ssh, genericbackend

LOG_SYSTEM = 'Force10'



COMMAND_ENABLE          = 'enable'
COMMAND_CONFIGURE       = 'configure'
COMMAND_END             = 'end'
COMMAND_EXIT            = 'exit'
COMMAND_WRITE           = 'write'       # writes config

COMMAND_INTERFACE_VLAN  = 'interface vlan %(vlan)i'
COMMAND_NAME            = 'name %(name)s'
COMMAND_NO_SHUTDOWN     = 'no shutdown'
COMMAND_TAGGED          = 'tagged %(interface)s'

COMMAND_NO_INTERFACE    = 'no interface vlan %(vlan)i'



def _portToInterfaceVLAN(nrm_port):

    interface, vlan = nrm_port.rsplit('.')
    vlan = int(vlan)
    return interface, vlan


def _createSetupCommands(source_nrm_port, dest_nrm_port):

    s_interface, s_vlan = _portToInterfaceVLAN(source_nrm_port)
    d_interface, d_vlan = _portToInterfaceVLAN(dest_nrm_port)

    assert s_vlan == d_vlan, 'Source and destination VLANs differ, unpossible!'

    name = 'opennsa-%i' % s_vlan

    cmd_vlan    = COMMAND_INTERFACE_VLAN    % { 'vlan' : s_vlan }
    cmd_name    = COMMAND_NAME              % { 'name' : name   }
    cmd_s_intf  = COMMAND_TAGGED            % { 'interface' : s_interface }
    cmd_d_intf  = COMMAND_TAGGED            % { 'interface' : d_interface }

    commands = [ cmd_vlan, cmd_name, cmd_s_intf, cmd_d_intf, COMMAND_NO_SHUTDOWN, COMMAND_END ]
    return commands


def _createTeardownCommands(source_nrm_port, dest_nrm_port):

    _, s_vlan = _portToInterfaceVLAN(source_nrm_port)
    _, d_vlan = _portToInterfaceVLAN(dest_nrm_port)

    assert s_vlan == d_vlan, 'Source and destination VLANs differ, unpossible!'

    cmd_no_intf = COMMAND_NO_INTERFACE % { 'vlan' : s_vlan }

    commands = [ cmd_no_intf, COMMAND_END ]
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
            term = os.environ.get('TERM', 'xterm')
	    winSize = (25,80,0,0)
	    ptyReqData = session.packRequest_pty_req(term, winSize, '')
            yield self.conn.sendRequest(self, 'pty-req', ptyReqData, wantReply=1)
            yield self.conn.sendRequest(self, 'shell', '', wantReply=1)
            log.msg('Got shell', system=LOG_SYSTEM, debug=True)

            d = self.waitForData('>')
            yield d
            log.msg('Got shell ready', system=LOG_SYSTEM, debug=True)

            # so far so good

            d = self.waitForData(':')
            self.write(COMMAND_ENABLE + LT) # This one fails for some reason
            yield d
            log.msg('Got enable password prompt', system=LOG_SYSTEM, debug=True)

            d = self.waitForData('#')
            self.write(enable_password + LT)
            yield d

            log.msg('Entered enabled mode', debug=True, system=LOG_SYSTEM)

            d = self.waitForData('#')
            self.write(COMMAND_CONFIGURE + LT) # This one fails for some reason
            yield d

            log.msg('Entered configure mode', debug=True, system=LOG_SYSTEM)

            for cmd in commands:
                log.msg('CMD> %s' % cmd, debug=True, system=LOG_SYSTEM)
                d = self.waitForData('#')
                self.write(cmd + LT)
                yield d

            # Superfluous COMMAND_END has been removed by hopet

            log.msg('Configuration done, writing configuration.', debug=True, system=LOG_SYSTEM)
            d = self.waitForData('#')
            self.write(COMMAND_WRITE + LT)
            yield d

            log.msg('Configuration written. Exiting.', debug=True, system=LOG_SYSTEM)
            self.write(COMMAND_EXIT + LT)
            # Waiting for the prompt removed by hopet - we could wait forever here! :(

        except Exception, e:
            log.msg('Error sending commands: %s' % str(e))
            raise e

        log.msg('Commands successfully send', system=LOG_SYSTEM)
        self.sendEOF()
        self.closeIt()


    def waitForData(self, data):
        self.wait_data  = data
        self.wait_defer = defer.Deferred()
        return self.wait_defer


    def dataReceived(self, data):
        log.msg("DATA:" + data, system=LOG_SYSTEM, debug=True)
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




class Force10CommandSender:

    def __init__(self, ssh_connection_creator, enable_password):

        self.ssh_connection_creator = ssh_connection_creator
        self.enable_password = enable_password


    @defer.inlineCallbacks
    def sendCommands(self, commands):

        # Note: FTOS does not allow multiple channels in an SSH connection,
        # so we open a connection for each request. Party like it is 1988.

        # The "correct" solution for this would be to create a connection pool,
        # but that won't happen just now.

        log.msg('Creating new SSH connection', debug=True, system=LOG_SYSTEM)
        ssh_connection = yield self.ssh_connection_creator.getSSHConnection()

        try:
            channel = SSHChannel(conn=ssh_connection)
            ssh_connection.openChannel(channel)
            log.msg("Opening channel", system=LOG_SYSTEM, debug=True)

            yield channel.channel_open
            log.msg("Channel open, sending commands", system=LOG_SYSTEM, debug=True)
            yield channel.sendCommands(commands, self.enable_password)

        finally:
            ssh_connection.transport.loseConnection()



class Force10ConnectionManager:

    def __init__(self, log_system, port_map, cfg):
        self.log_system = log_system
        self.port_map   = port_map

        host             = cfg[config.FORCE10_HOST]
        port             = cfg.get(config.FORCE10_PORT, 22)
        host_fingerprint = cfg[config.FORCE10_HOST_FINGERPRINT]
        user             = cfg[config.FORCE10_USER]


        if config.FORCE10_PASSWORD in cfg:
            password = cfg[config.FORCE10_PASSWORD]
            ssh_connection_creator = ssh.SSHConnectionCreator(host, port, [ host_fingerprint ], user, password=password)

        else:
            ssh_public_key   = cfg[config.FORCE10_SSH_PUBLIC_KEY]
            ssh_private_key  = cfg[config.FORCE10_SSH_PRIVATE_KEY]
            ssh_connection_creator = ssh.SSHConnectionCreator(host, port, [ host_fingerprint ], user, ssh_public_key, ssh_private_key)

        # this will blow up when used with ssh keys
        self.command_sender = Force10CommandSender(ssh_connection_creator, enable_password=password)


    def getResource(self, port, label_type, label_value):
        assert label_type == cnt.ETHERNET_VLAN, 'Label type must be ethernet-vlan'
        return str(label_value)


    def getTarget(self, port, label_type, label_value):
        return self.port_map[port] + '.' + label_value


    def createConnectionId(self, source_target, dest_target):
        return 'F10-' + ''.join( [ random.choice(string.hexdigits[:16]) for _ in range(10) ] )


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



def Force10Backend(network_name, network_topology, parent_requester, port_map, configuration):
    name = 'Force10 %s' % network_name
    cm = Force10ConnectionManager(name, port_map, configuration)
    return genericbackend.GenericBackend(network_name, network_topology, cm, parent_requester, name)
