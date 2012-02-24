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

Copyright: NORDUnet (2011-2012)
"""

from twisted.python import log
from twisted.internet import defer

from opennsa import error, config
from opennsa.backends.common import calendar as reservationcalendar, simplebackend, ssh



LOG_SYSTEM = 'opennsa.force10'



COMMAND_CONFIGURE       = 'configure'
COMMAND_END             = 'end'

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

    commands = [ cmd_vlan, cmd_name, COMMAND_NO_SHUTDOWN, cmd_s_intf, cmd_d_intf ]
    return commands


def _createTeardownCommands(source_nrm_port, dest_nrm_port):

    _, s_vlan = _portToInterfaceVLAN(source_nrm_port)
    _, d_vlan = _portToInterfaceVLAN(dest_nrm_port)

    assert s_vlan == d_vlan, 'Source and destination VLANs differ, unpossible!'

    cmd_no_intf = COMMAND_NO_INTERFACE % { 'vlan' : s_vlan }

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
    def sendCommands(self, commands):
        LT = '\r' # line termination

        try:
            log.msg('Requesting shell for sending commands', debug=True, system=LOG_SYSTEM)
            yield self.conn.sendRequest(self, 'shell', '', wantReply=1)

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

        except Exception, e:
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




class Force10CommandSender:

    def __init__(self, host, port, ssh_host_fingerprint, user, ssh_public_key_path, ssh_private_key_path):

        self.ssh_connection_creator = \
             ssh.SSHConnectionCreator(host, port, [ ssh_host_fingerprint ], user, ssh_public_key_path, ssh_private_key_path)


    @defer.inlineCallbacks
    def _sendCommands(self, commands):

        # Note: FTOS does not allow multiple channels in an SSH connection,
        # so we open a connection for each request. Party like it is 1988.

        # The "correct" solution for this would be to create a connection pool,
        # but that won't happen just now.

        log.msg('Creating new SSH connection', debug=True, system=LOG_SYSTEM)
        ssh_connection = yield self.ssh_connection_creator.getSSHConnection()

        try:
            channel = SSHChannel(conn=ssh_connection)
            ssh_connection.openChannel(channel)

            yield channel.channel_open
            yield channel.sendCommands(commands)

        finally:
            ssh_connection.transport.loseConnection()


    def setupLink(self, source_nrm_port, dest_nrm_port):

        log.msg('Setting up link: %s-%s' % (source_nrm_port, dest_nrm_port), debug=True, system=LOG_SYSTEM)
        commands = _createSetupCommands(source_nrm_port, dest_nrm_port)
        return self._sendCommands(commands)


    def teardownLink(self, source_nrm_port, dest_nrm_port):

        log.msg('Tearing down link: %s-%s' % (source_nrm_port, dest_nrm_port), debug=True, system=LOG_SYSTEM)
        commands = _createTeardownCommands(source_nrm_port, dest_nrm_port)
        return self._sendCommands(commands)



class Force10Backend:

    def __init__(self, network_name, configuration):
        self.network_name = network_name
        self.calendar = reservationcalendar.ReservationCalendar()

        # extract config items
        cfg_dict = dict(configuration)

        host             = cfg_dict[config.FORCE10_HOST]
        port             = cfg_dict.get(config.FORCE10_PORT, 22)
        host_fingerprint = cfg_dict[config.FORCE10_HOST_FINGERPRINT]
        user             = cfg_dict[config.FORCE10_USER]
        ssh_public_key   = cfg_dict[config.FORCE10_SSH_PUBLIC_KEY]
        ssh_private_key  = cfg_dict[config.FORCE10_SSH_PRIVATE_KEY]

        self.command_sender = Force10CommandSender(host, port, host_fingerprint, user, ssh_public_key, ssh_private_key)


    def createConnection(self, source_nrm_port, dest_nrm_port, service_parameters):

        self._checkVLANMatch(source_nrm_port, dest_nrm_port)

        # probably need a short hand for this
        self.calendar.checkReservation(source_nrm_port, service_parameters.start_time, service_parameters.end_time)
        self.calendar.checkReservation(dest_nrm_port  , service_parameters.start_time, service_parameters.end_time)

        self.calendar.addConnection(source_nrm_port, service_parameters.start_time, service_parameters.end_time)
        self.calendar.addConnection(dest_nrm_port  , service_parameters.start_time, service_parameters.end_time)

        c = simplebackend.GenericConnection(source_nrm_port, dest_nrm_port, service_parameters, self.network_name, self.calendar,
                                            'Force10 NRM', LOG_SYSTEM, self.command_sender)
        return c


    def _checkVLANMatch(self, source_nrm_port, dest_nrm_port):
        source_vlan = source_nrm_port.split('.')[-1]
        dest_vlan = dest_nrm_port.split('.')[-1]
        if source_vlan != dest_vlan:
            raise error.InvalidRequestError('Cannot create connection between different VLANs (%s/%s).' % (source_vlan, dest_vlan) )

