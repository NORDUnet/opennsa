"""
Backend for Dell Powerswitch 5324 Switch. May work with similar equipment.

Author: Jeroen van der Ham
Copyright: NORDUnet (2012-2013)
"""

# OpenNSA JunOS backend.
# User Name:admin
# Password:*******
#
## configure snippet:
#
# eth-sw4# configure <return>
# eth-sw4(config)# switchport mode 


from twisted.python import log
from twisted.internet import defer

from opennsa import config
from opennsa.backends.common import calendar as reservationcalendar, simplebackend, ssh


# parameterized commands
USERNAME = "admin"
PASSWORD = "tip2013"
COMMAND_CONFIGURE        = 'configure'
COMMAND_CONFIGURE_PORT = 'interface ethernet %(port)s' # port
COMMAND_ADD_VLAN    = 'switchport general allowed vlan add %(vlan)s' # vlan
COMMAND_DELETE_VLAN = 'switchport general allowed vlan remove %(vlan)s' # vlan
COMMAND_END = 'exit'

LOG_SYSTEM = 'opennsa.Dell'


def portToInterfaceVLAN(nrm_port):

    port, vlan = nrm_port.split('.')
    return port, vlan


def createConfigureCommands(source_nrm_port, dest_nrm_port):
    source_port, source_vlan = portToInterfaceVLAN(source_nrm_port)
    dest_port,   dest_vlan   = portToInterfaceVLAN(dest_nrm_port)
    cfg_port_source = COMMAND_CONFIGURE_PORT % {'port': source_port}
    cfg_port_source_vlan = COMMAND_ADD_VLAN  % {'vlan': source_vlan}

    cfg_port_dest = COMMAND_CONFIGURE_PORT % {'port': dest_port}
    cfg_port_dest_vlan = COMMAND_ADD_VLAN % {'vlan': dest_vlan}

    commands = [ cfg_port_source, cfg_port_source_vlan, COMMAND_END, cfg_port_dest, cfg_port_dest_vlan ]
    return commands


def createDeleteCommands(source_nrm_port, dest_nrm_port):
    source_port, source_vlan = portToInterfaceVLAN(source_nrm_port)
    dest_port,   dest_vlan   = portToInterfaceVLAN(dest_nrm_port)
    cfg_port_source = COMMAND_CONFIGURE_PORT % {'port': source_port}
    cfg_port_source_vlan = COMMAND_DELETE_VLAN  % {'vlan': source_vlan}

    cfg_port_dest = COMMAND_CONFIGURE_PORT % {'port': dest_port}
    cfg_port_dest_vlan = COMMAND_DELETE_VLAN % {'vlan': dest_vlan}

    commands = [ cfg_port_source, cfg_port_source_vlan, COMMAND_END, cfg_port_dest, cfg_port_dest_vlan ]
    return commands



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

            d = self.waitForData('User Name:')
            self.write(USERNAME + LT)
            d = self.waitForData('Password:')
            self.write(PASSWORD + LT)
            d = self.waitForData('#')
            self.write(COMMAND_CONFIGURE + LT)
            yield d

            log.msg('Entered configure mode', debug=True, system=LOG_SYSTEM)

            for cmd in commands:
                log.msg('CMD> %s' % cmd, system=LOG_SYSTEM)
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



class DellCommandSender:


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

        if self.ssh_connection:
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


    def setupLink(self, source_nrm_port, dest_nrm_port):

        commands = createConfigureCommands(source_nrm_port, dest_nrm_port)
        return self._sendCommands(commands)


    def teardownLink(self, source_nrm_port, dest_nrm_port):

        commands = createDeleteCommands(source_nrm_port, dest_nrm_port)
        return self._sendCommands(commands)


# --------


class DellBackend:

    def __init__(self, network_name, configuration):
        self.network_name = network_name
        self.calendar = reservationcalendar.ReservationCalendar()

        # extract config items
        cfg_dict = dict(configuration)

        host             = cfg_dict[config.DELL_HOST]
        port             = cfg_dict.get(config.DELL_PORT, 22)
        host_fingerprint = cfg_dict[config.DELL_HOST_FINGERPRINT]
        user             = cfg_dict[config.DELL_USER]
        ssh_public_key   = cfg_dict[config.DELL_SSH_PUBLIC_KEY]
        ssh_private_key  = cfg_dict[config.DELL_SSH_PRIVATE_KEY]

        self.command_sender = DellCommandSender(host, port, host_fingerprint, user, ssh_public_key, ssh_private_key)


    def createConnection(self, source_nrm_port, dest_nrm_port, service_parameters):

        src_port, src_vlan = portToInterfaceVLAN(source_nrm_port)
        dst_port, dst_vlan = portToInterfaceVLAN(dest_nrm_port)

        if src_vlan != dst_vlan:
            raise error.VLANInterchangeNotSupportedError('VLAN rewrite not supported on this ancient dell switch')

        self.calendar.checkReservation(source_nrm_port, service_parameters.start_time, service_parameters.end_time)
        self.calendar.checkReservation(dest_nrm_port  , service_parameters.start_time, service_parameters.end_time)
        # since vlan are a global switching domain we also need to do a reservation for the vlan in the time period
        vlan_resource = 'vlan#' + src_vlan
        self.calendar.checkReservation(vlan_resource  , service_parameters.start_time, service_parameters.end_time)

        self.calendar.addConnection(source_nrm_port, service_parameters.start_time, service_parameters.end_time)
        self.calendar.addConnection(dest_nrm_port  , service_parameters.start_time, service_parameters.end_time)

        c = simplebackend.GenericConnection(source_nrm_port, dest_nrm_port, service_parameters, self.network_name, self.calendar,
                                            'Dell NRM', LOG_SYSTEM, self.command_sender)
        return c

