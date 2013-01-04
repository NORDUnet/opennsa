"""
Brocade backend.
Contributed by Balasubramania Pillai from MAX Gigapop.

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

from twisted.python import log
from twisted.internet import defer

from opennsa import error, config
from opennsa.backends.common import calendar as reservationcalendar, simplebackend, ssh

LOG_SYSTEM = 'opennsa.brocade'


COMMAND_PRIVILEGE   = 'enable privileged'
COMMAND_CONFIGURE   = 'configure terminal'
COMMAND_END         = 'end'

COMMAND_VLAN        = 'vlan %(vlan)i name %(name)s'
COMMAND_TAGGED      = 'tagged %(port)s'

COMMAND_NO_VLAN     = 'no vlan %(vlan)i'


def _portToInterfaceVLAN(nrm_port):

    prefix_str, port_vlan_str = nrm_port.split('::')
    port, vlan = port_vlan_str.split('.')
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
    def sendCommands(self, commands):
        LT = '\r' # line termination

        try:
            log.msg('Requesting shell for sending commands', debug=True, system=LOG_SYSTEM)
            yield self.conn.sendRequest(self, 'shell', '', wantReply=1)

            d = self.waitForData('>')
            self.write(COMMAND_PRIVILEGE + LT)
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




class BrocadeCommandSender:

    def __init__(self, host, port, ssh_host_fingerprint, user, ssh_public_key_path, ssh_private_key_path):

        self.ssh_connection_creator = \
             ssh.SSHConnectionCreator(host, port, [ ssh_host_fingerprint ], user, ssh_public_key_path, ssh_private_key_path)


    @defer.inlineCallbacks
    def _sendCommands(self, commands):

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
            yield channel.sendCommands(commands)

        finally:
            ssh_connection.transport.loseConnection()


    def setupLink(self, source_nrm_port, dest_nrm_port):

        log.msg('setupLink: src %s dst %s' % (source_nrm_port, dest_nrm_port))


        commands = _createSetupCommands(source_nrm_port, dest_nrm_port)
        return self._sendCommands(commands)


    def teardownLink(self, source_nrm_port, dest_nrm_port):

        commands = _createTeardownCommands(source_nrm_port, dest_nrm_port)
        return self._sendCommands(commands)



class BrocadeBackend:

    def __init__(self, network_name, configuration):
        self.network_name = network_name
        self.calendar = reservationcalendar.ReservationCalendar()

        # extract config items
        cfg_dict = dict(configuration)

        host             = cfg_dict[config.BROCADE_HOST]
        port             = cfg_dict.get(config.BROCADE_PORT, 22)
        host_fingerprint = cfg_dict[config.BROCADE_HOST_FINGERPRINT]
        user             = cfg_dict[config.BROCADE_USER]
        ssh_public_key   = cfg_dict[config.BROCADE_SSH_PUBLIC_KEY]
        ssh_private_key  = cfg_dict[config.BROCADE_SSH_PRIVATE_KEY]

        self.command_sender = BrocadeCommandSender(host, port, host_fingerprint, user, ssh_public_key, ssh_private_key)


    def createConnection(self, source_nrm_port, dest_nrm_port, service_parameters):

        self._checkVLANMatch(source_nrm_port, dest_nrm_port)

        # probably need a short hand for this
        self.calendar.checkReservation(source_nrm_port, service_parameters.start_time, service_parameters.end_time)
        self.calendar.checkReservation(dest_nrm_port  , service_parameters.start_time, service_parameters.end_time)

        self.calendar.addConnection(source_nrm_port, service_parameters.start_time, service_parameters.end_time)
        self.calendar.addConnection(dest_nrm_port  , service_parameters.start_time, service_parameters.end_time)

        c = simplebackend.GenericConnection(source_nrm_port, dest_nrm_port, service_parameters, self.network_name, self.calendar,
                                            'Brocade', LOG_SYSTEM, self.command_sender)
        return c


    def _checkVLANMatch(self, source_nrm_port, dest_nrm_port):
        source_vlan = source_nrm_port.split('.')[-1]
        dest_vlan = dest_nrm_port.split('.')[-1]
        if source_vlan != dest_vlan:
            raise error.VLANInterchangeNotSupportedError('Cannot create connection between different VLANs (%s/%s).' % (source_vlan, dest_vlan) )

