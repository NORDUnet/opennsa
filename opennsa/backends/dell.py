"""
Backend for Dell PowerConnect 5324 Switch. May work with similar equipment.

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
from twisted.internet import defer, endpoints, reactor
from twisted.internet.protocol import ClientFactory
from twisted.conch.telnet import TelnetProtocol

from opennsa import error, config
from opennsa.backends.common import calendar as reservationcalendar, simplebackend


# parameterized commands
COMMAND_CONFIGURE        = 'configure'
COMMAND_CONFIGURE_PORT = 'interface ethernet %(port)s' # port
COMMAND_ADD_VLAN    = 'switchport general allowed vlan add %(vlan)s' # vlan
COMMAND_DELETE_VLAN = 'switchport general allowed vlan remove %(vlan)s' # vlan
COMMAND_EXIT = 'exit'

LOG_SYSTEM = 'Dell'


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

    commands = [ cfg_port_source, cfg_port_source_vlan, COMMAND_EXIT, cfg_port_dest, cfg_port_dest_vlan, COMMAND_EXIT ]
    return commands


def createDeleteCommands(source_nrm_port, dest_nrm_port):
    source_port, source_vlan = portToInterfaceVLAN(source_nrm_port)
    dest_port,   dest_vlan   = portToInterfaceVLAN(dest_nrm_port)
    cfg_port_source = COMMAND_CONFIGURE_PORT % {'port': source_port}
    cfg_port_source_vlan = COMMAND_DELETE_VLAN  % {'vlan': source_vlan}

    cfg_port_dest = COMMAND_CONFIGURE_PORT % {'port': dest_port}
    cfg_port_dest_vlan = COMMAND_DELETE_VLAN % {'vlan': dest_vlan}

    commands = [ cfg_port_source, cfg_port_source_vlan, COMMAND_EXIT, cfg_port_dest, cfg_port_dest_vlan, COMMAND_EXIT ]
    return commands



class DellTelnetProtocol(TelnetProtocol):

    def __init__(self, username, password):

        self.username = username
        self.password = password

        self.data = ''
        self.wait_defer = None
        self.wait_data  = None


    def connectionMade(self):
        log.msg('Telnet connection made', system=LOG_SYSTEM)


    @defer.inlineCallbacks
    def sendCommands(self, commands):
        LT = '\r' # line termination

        log.msg("Sending commands", system=LOG_SYSTEM)

        try:
            d = self.waitForData('User Name:')
            yield d
            #log.msg("Got user name request", system=LOG_SYSTEM)
            self.transport.write(self.username + LT)

            d = self.waitForData('Password:')
            yield d
            #log.msg("Got password request", system=LOG_SYSTEM)
            self.transport.write(self.password + LT)

            d = self.waitForData('#')
            self.transport.write(COMMAND_CONFIGURE + LT)
            yield d
            #log.msg("Got configure shell", system=LOG_SYSTEM)

            log.msg('Entered configure mode', debug=True, system=LOG_SYSTEM)

            for cmd in commands:
                log.msg('CMD> %s' % cmd, system=LOG_SYSTEM)
                d = self.waitForData('#')
                self.transport.write(cmd + LT)
                yield d
                # failure handling - i don't think so

            log.msg('Commands send, sending exit command.', debug=True, system=LOG_SYSTEM)

            # exit configure mode
            d = self.waitForData('#')
            self.transport.write(COMMAND_EXIT + LT)
            yield d

            # exit from device, this will make it drop the connection, so we don't wait for anything
            self.transport.write(COMMAND_EXIT + LT)
 
        except Exception, e:
            log.msg('Error sending commands: %s' % str(e))
            raise e

        log.msg('Commands successfully send', debug=True, system=LOG_SYSTEM)
        self.transport.loseConnection()

    def waitForData(self, data):
        #log.msg('WFD: ' + data, system=LOG_SYSTEM)
        self.wait_data  = data
        self.wait_defer = defer.Deferred()
        return self.wait_defer


    def dataReceived(self, data):
        #print 'RX: ', data

        if len(data) == 0:
            pass
        else:
            self.data += data
            if self.wait_data and self.wait_data in self.data:
                #print 'Data trigger: ' + self.wait_data
                d = self.wait_defer
                self.data       = ''
                self.wait_data  = None
                self.wait_defer = None
                d.callback(self)



class TelnetFactory(ClientFactory):

    def __init__(self, username, password):
        self.username = username
        self.password = password

    def buildProtocol(self, addr):

        return DellTelnetProtocol(self.username, self.password)


class DellCommandSender:


    def __init__(self, host, port, username, password):

        self.host = host
        self.port = port
        self.username = username
        self.password = password


    def _sendCommands(self, commands):

        def gotProtocol(proto):
            log.msg('Telnet protocol created', debug=True, system=LOG_SYSTEM)
            d = proto.sendCommands(commands)
            return d

        log.msg('Creating telnet connection', debug=True, system=LOG_SYSTEM)

        factory = TelnetFactory(self.username, self.password)

        point = endpoints.TCP4ClientEndpoint(reactor, self.host, self.port)
        d = point.connect(factory)
        d.addCallback(gotProtocol)
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
        port             = cfg_dict.get(config.DELL_PORT, 23)
        user             = cfg_dict[config.DELL_USER]
        password         = cfg_dict[config.DELL_PASSWORD]

        self.command_sender = DellCommandSender(host, port, user, password)


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

