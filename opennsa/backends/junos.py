"""
OpenNSA JunOS / Juniper MX backend.

Note: Has NOT been ported to new backend interface.
"""

# configure snippet:

# opennsa@cph> configure <return>
# Entering configuration mode
#
#[edit]
#
#opennsa@cph# set protocols connections interface-switch ps-to-netherlight-1780 interface ge-1/0/5.1780
#
#[edit]
#
#opennsa@cph# set interfaces ge-1/0/5 unit 1780 vlan-id 1780 encapsulation vlan-ccc
#
#[edit]
#opennsa@cph# delete interfaces ge-1/0/5 unit 1780
#
#[edit]
#opennsa@cph# delete protocols connections interface-switch ps-to-netherlight-1780
#
#[edit]
#
# Basically stuff should end with [edit] :-)
#

from twisted.python import log
from twisted.internet import defer

from opennsa import config
from opennsa.backends.common import calendar as reservationcalendar, simplebackend, ssh


# Example commands used:
#> set protocols connections interface-switch ps-to-netherlight-1780 interface ge-1/0/5.1780
#> set protocols connections interface-switch ps-to-netherlight-1780 interface ge-1/1/9.1780
#> set interfaces ge-1/0/5 unit 1780 vlan-id 1780 encapsulation vlan-ccc
#> set interfaces ge-1/1/9 unit 1780 vlan-id 1780 encapsulation vlan-ccc

# VLAN swapping
#> set interfaces ge-1/1/9 unit 1780 vlan-id 1780 encapsulation vlan-ccc input-vlan-map swap vlan-id 1781
#> set interfaces ge-1/1/9 unit 1781 vlan-id 1781 encapsulation vlan-ccc input-vlan-map swap vlan-id 1780

# parameterized commands
COMMAND_CONFIGURE           = 'configure'
COMMAND_COMMIT              = 'commit'

COMMAND_SET_CONNECTIONS     = 'set protocols connections interface-switch %(switch)s interface %(interface)s' # switch name, interface
COMMAND_SET_INTERFACES      = 'set interfaces %(port)s unit %(source_vlan)s vlan-id %(source_vlan)s encapsulation vlan-ccc' # port, source vlan, source vlan
COMMAND_SET_INTERFACES_SWAP = 'set interfaces %(port)s unit %(source_vlan)s vlan-id %(source_vlan)s encapsulation vlan-ccc input-vlan-map swap vlan-id %(dest_vlan)s' # port, source vlan, source vlan, dest vlan

COMMAND_DELETE_INTERFACES   = 'delete interfaces %(port)s unit %(vlan)s' # port / vlan
COMMAND_DELETE_CONNECTIONS  = 'delete protocols connections interface-switch %(switch)s' # switch

LOG_SYSTEM = 'opennsa.JunOS'


def portToInterfaceVLAN(nrm_port):

    port, vlan = nrm_port.split('.')
    return port, vlan


def createSwitchName(source_port, dest_port, source_vlan, dest_vlan):

    sp = source_port.replace('/','').replace('-','')
    dp = dest_port.replace('/','').replace('-','')

    switch_name = 'nsi-%s-%s-%s-%s' % (sp, source_vlan, dp, dest_vlan)
    return switch_name


def createConfigureCommands(source_nrm_port, dest_nrm_port):

    source_port, source_vlan = portToInterfaceVLAN(source_nrm_port)
    dest_port,   dest_vlan   = portToInterfaceVLAN(dest_nrm_port)

    switch_name = createSwitchName(source_port, dest_port, source_vlan, dest_vlan)

    cfg_conn_source = COMMAND_SET_CONNECTIONS % { 'switch':switch_name, 'interface':source_nrm_port }
    cfg_conn_dest   = COMMAND_SET_CONNECTIONS % { 'switch':switch_name, 'interface':dest_nrm_port   }

    if source_vlan == dest_vlan:
        cfg_intf_source = COMMAND_SET_INTERFACES % { 'port':source_port, 'source_vlan': source_vlan }
        cfg_intf_dest   = COMMAND_SET_INTERFACES % { 'port':dest_port,   'source_vlan': dest_vlan   }
    else:
        cfg_intf_source = COMMAND_SET_INTERFACES_SWAP % { 'port':source_port, 'source_vlan':source_vlan, 'dest_vlan':dest_vlan }
        cfg_intf_dest   = COMMAND_SET_INTERFACES_SWAP % { 'port':dest_port,   'source_vlan':dest_vlan,   'dest_vlan':source_vlan }

    commands = [ cfg_conn_source, cfg_conn_dest, cfg_intf_source, cfg_intf_dest ]
    return commands


def createDeleteCommands(source_nrm_port, dest_nrm_port):

    source_port, source_vlan = portToInterfaceVLAN(source_nrm_port)
    dest_port,   dest_vlan   = portToInterfaceVLAN(dest_nrm_port)

    switch_name = createSwitchName(source_port, dest_port, source_vlan, dest_vlan)

    del_intf_source = COMMAND_DELETE_INTERFACES  % {'port':source_port, 'vlan': source_vlan }
    del_intf_dest   = COMMAND_DELETE_INTERFACES  % {'port':dest_port,   'vlan': dest_vlan   }
    del_conn        = COMMAND_DELETE_CONNECTIONS % {'switch':switch_name }

    commands = [ del_intf_source, del_intf_dest, del_conn ]
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

            d = self.waitForLine('[edit]')
            self.write(COMMAND_CONFIGURE + LT)
            yield d

            log.msg('Entered configure mode', debug=True, system=LOG_SYSTEM)

            for cmd in commands:
                log.msg('CMD> %s' % cmd, system=LOG_SYSTEM)
                d = self.waitForLine('[edit]')
                self.write(cmd + LT)
                yield d

            # commit commands, check for 'commit complete' as success
            # not quite sure how to handle failure here

            ## test stuff
            #d = self.waitForLine('[edit]')
            #self.write('commit check' + LT)

            d = self.waitForLine('commit complete')
            self.write(COMMAND_COMMIT + LT)
            yield d

        except Exception, e:
            log.msg('Error sending commands: %s' % str(e))
            raise e

        log.msg('Commands successfully committed', debug=True, system=LOG_SYSTEM)
        self.sendEOF()
        self.closeIt()


    def waitForLine(self, line):
        self.wait_line = line
        self.wait_defer = defer.Deferred()
        return self.wait_defer


    def matchLine(self, line):
        if self.wait_line and self.wait_defer:
            if self.wait_line == line.strip():
                d = self.wait_defer
                self.wait_line  = None
                self.wait_defer = None
                d.callback(self)
            else:
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




class JunOSCommandSender:


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


class JunOSBackend:

    def __init__(self, network_name, configuration):
        self.network_name = network_name
        self.calendar = reservationcalendar.ReservationCalendar()

        # extract config items
        cfg_dict = dict(configuration)

        host             = cfg_dict[config.JUNOS_HOST]
        port             = cfg_dict.get(config.JUNOS_PORT, 22)
        host_fingerprint = cfg_dict[config.JUNOS_HOST_FINGERPRINT]
        user             = cfg_dict[config.JUNOS_USER]
        ssh_public_key   = cfg_dict[config.JUNOS_SSH_PUBLIC_KEY]
        ssh_private_key  = cfg_dict[config.JUNOS_SSH_PRIVATE_KEY]

        self.command_sender = JunOSCommandSender(host, port, host_fingerprint, user, ssh_public_key, ssh_private_key)


    def createConnection(self, source_nrm_port, dest_nrm_port, service_parameters):

        # probably need a short hand for this
        self.calendar.checkReservation(source_nrm_port, service_parameters.start_time, service_parameters.end_time)
        self.calendar.checkReservation(dest_nrm_port  , service_parameters.start_time, service_parameters.end_time)

        self.calendar.addConnection(source_nrm_port, service_parameters.start_time, service_parameters.end_time)
        self.calendar.addConnection(dest_nrm_port  , service_parameters.start_time, service_parameters.end_time)

        c = simplebackend.GenericConnection(source_nrm_port, dest_nrm_port, service_parameters, self.network_name, self.calendar,
                                            'JunOS NRM', LOG_SYSTEM, self.command_sender)
        return c

