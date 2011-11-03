"""
OpenNSA JunOS backend.
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

import StringIO

from twisted.internet import defer, protocol, reactor, endpoints
from twisted.conch import error
from twisted.conch.ssh import common, transport, keys, userauth, connection, channel

# Stuff to get from config:

JUNOS_HOST              = 'cph.dcn.nordu.net'
JUNOS_HOST_PORT         = 22
JUNOS_HOST_FINGERPRINT  = 'd8:43:73:ee:a4:87:87:36:3f:c4:e5:3e:7c:d9:8b:d7'

USERNAME                = 'opennsa'
PUBLIC_KEY_PATH         = '/home/opennsa/.ssh/id_rsa.pub'
PRIVATE_KEY_PATH        = '/home/opennsa/.ssh/id_rsa'

# commands - parametize these later
COMMAND_CONFIGURE           = 'configure'
COMMAND_SET_CONNECTIONS     = 'set protocols connections interface-switch ps-to-netherlight-1780 interface ge-1/0/5.1780' # connection name / interface
COMMAND_SET_INTERFACES      = 'set interfaces ge-1/0/5 unit 1780 vlan-id 1780 encapsulation vlan-ccc'
COMMAND_DELETE_INTERFACE    = 'delete interfaces ge-1/1/9 unit 1780'
COMMAND_DELETE_CONNECTIONS  = 'delete protocols connections interface-switch ps-to-netherlight-1780'




class SSHClientTransport(transport.SSHClientTransport):

    def __init__(self, fingerprints=None):
        self.fingerprints = fingerprints or []
        self.secure_defer = defer.Deferred()


    def verifyHostKey(self, public_key, fingerprint):
        if fingerprint in self.fingerprints:
            return defer.succeed(1)
        else:
            return defer.fail(error.ConchError('Fingerprint not accepted'))


    def connectionSecure(self):
        self.secure_defer.callback(self)



class SSHClientFactory(protocol.ClientFactory):

    protocol = SSHClientTransport

    def __init__(self, fingerprints=None):
        # ClientFactory has no __init__ method, so we don't call it
        self.fingerprints = fingerprints or []


    def buildProtocol(self, addr):

        p = self.protocol(self.fingerprints)
        p.factory = self
        return p



class ClientUserAuth(userauth.SSHUserAuthClient):

    def __init__(self, user, connection, public_key_path, private_key_path):
        userauth.SSHUserAuthClient.__init__(self, user, connection)
        self.public_key_path    = public_key_path
        self.private_key_path   = private_key_path

    def getPassword(self, prompt = None):
        return # this says we won't do password authentication

    def getPublicKey(self):
        return keys.Key.fromFile(self.public_key_path)

    def getPrivateKey(self):
        return defer.succeed( keys.Key.fromFile(self.private_key_path) )



class SSHConnection(connection.SSHConnection):

    def __init__(self):
        connection.SSHConnection.__init__(self)
        self.service_started = defer.Deferred()

    def serviceStarted(self):
        self.service_started.callback(self)



class SSHChannel(channel.SSHChannel):

    name = 'session'

    def __init__(self, localWindow = 0, localMaxPacket = 0, remoteWindow = 0, remoteMaxPacket = 0, conn = None, data=None, avatar = None):
        channel.SSHChannel.__init__(self, localWindow = 0, localMaxPacket = 0, remoteWindow = 0, remoteMaxPacket = 0, conn = None, data=None, avatar = None)
        self.channel_open = defer.Deferred()
        self.data = None

    def channelOpen(self, data):
        self.data = StringIO.StringIO()
        self.channel_open.callback(self)
        #print "CHANNEL OPEN"

    def ping(self):
        #print "PING"
        d = self.conn.sendRequest(self, 'exec', common.NS('ping orval.grid.aau.dk count 2'), wantReply = 1)
        d.addCallback(self.sendEOF)
        d.addCallback(self.closeIt)
        return d

    def sendEOF(self, passthru):
        #print "# SENDING EOF"
        self.conn.sendEOF(self)
        return passthru

    def closeIt(self, passthru):
        #self.conn.transport.loseConnection()
        return passthru

    def dataReceived(self, data):
        print "#", len(data)
        #self.catData += data
        self.data.write(data)

    def eofReceived(self):
        #print "EOF RECEIVED"
        self.data.seek(0)
        print self.data.read()

    def closed(self):
        pass
        #print "# SSH Connection closed"





class JunOSCommandSender:


    def __init__(self):
        self.client = None
        self.proto  = None


    def createSSHConnection(self):

        def transportSecure(client, proto):
            return proto

        def gotProtocol(proto):
            proto.secure_defer.addCallback(transportSecure, proto)
            return proto.secure_defer

        # should check if there is an existing protocol in place

        factory = SSHClientFactory( [ JUNOS_HOST_FINGERPRINT ] )
        point = endpoints.TCP4ClientEndpoint(reactor, JUNOS_HOST, JUNOS_HOST_PORT)
        d = point.connect(factory)
        d.addCallback(gotProtocol)
        return d


    def getSSHChannel(self):

        def serviceStarted(connection):
            channel = SSHChannel(conn = connection)
            connection.openChannel(channel)
            return channel.channel_open

        def gotProtocol(proto):
            ssh_connection = SSHConnection()
            proto.requestService(ClientUserAuth(USERNAME, ssh_connection, PUBLIC_KEY_PATH, PRIVATE_KEY_PATH))
            ssh_connection.service_started.addCallback(serviceStarted)
            return ssh_connection.service_started

        d = self.createSSHConnection()
        d.addCallback(gotProtocol)
        return d


    def reserve(self, source_port, dest_port, start_time, end_time):

        def gotChannel(channel):
            d = channel.ping()
            return d

        d = self.getSSHChannel()
        d.addCallback(gotChannel)
        return d


# --------


class JunOSBackend:

    def __init__(self, network_name):
        self.network_name = network_name
        self.command_sender = JunOSCommandSender()


    def createConnection(self, source_port, dest_port, service_parameters):

        c = JunOSConnection(source_port, dest_port, service_parameters, self.command_sender)
        return c



class JunOSConnection:

    def __init__(self, source_port, dest_port, service_parameters, command_sender):
        self.source_port = source_port
        self.dest_port = dest_port
        self.service_parameters = service_parameters
        self.command_sender = command_sender


    def stps(self):
        return self.service_parameters.source_stp, self.service_parameters.dest_stp


    def reserve(self):

        #print self.service_parameters
        d = self.command_sender.reserve(self.source_port, self.dest_port, self.service_parameters.start_time, self.service_parameters.end_time)

        return defer.fail(NotImplementedError('constructing..'))


    def provision(self):
        err = NotImplementedError('constructing..')
        return defer.fail(err)


    def release(self):
        err = NotImplementedError('constructing..')
        return defer.fail(err)


    def terminate(self):
        err = NotImplementedError('constructing..')
        return defer.fail(err)


