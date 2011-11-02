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
        self.client_connection = None


    def verifyHostKey(self, public_key, fingerprint):
        if fingerprint in self.fingerprints:
            return defer.succeed(1)
        else:
            return defer.fail(error.ConchError('Fingerprint not accepted'))


    def connectionSecure(self):
        self.client_connection = ClientConnection()
        self.requestService(ClientUserAuth(USERNAME, self.client_connection, PUBLIC_KEY_PATH, PRIVATE_KEY_PATH))




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



class ClientConnection(connection.SSHConnection):

    def serviceStarted(self):
        print "SERVICE START"
        self.openChannel(ConfigureChannel(conn = self))



class ConfigureChannel(channel.SSHChannel):

    name = 'session'

    def channelOpen(self, data):
        #d = self.conn.sendRequest(self, 'exec', common.NS('configure'), wantReply = 1)
        pass # don't do anything now, wait until we get a request
        return self.ping()


    def ping(self):
        d = self.conn.sendRequest(self, 'exec', common.NS('ping orval.grid.aau.dk count 2'), wantReply = 1)
        d.addCallback(self.sendEOF)
        d.addCallback(self.closeIt)
        return d
#        d.addCallback(self._cbSendRequest)
#        self.catData = ''

    def sendEOF(self, passthru):
        print "# SENDING EOF"
        self.conn.sendEOF(self)
        return passthru


    def closeIt(self, passthru):
        #self.conn.transport.loseConnection()
        return passthru

    def dataReceived(self, data):
        print "#", data,
        #self.catData += data

    def closed(self):
        print "# SSH Connection closed"
#        print 'We got this from "cat":', self.catData








class JunOSBackend:

    def __init__(self, network_name):
        self.network_name = network_name


    def createSSHConnection(self):

        #factory = protocol.ClientFactory()
        #factory.protocol = ClientTransport
        #connector = reactor.connectTCP(JUNOS_HOST, JUNOS_HOST_PORT, factory)
        #print dir(connector)
        #return factory

        factory = SSHClientFactory( [ JUNOS_HOST_FINGERPRINT ] )
        point = endpoints.TCP4ClientEndpoint(reactor, JUNOS_HOST, JUNOS_HOST_PORT)
        d = point.connect(factory)
        return d


    def getSSHChannel(self):

        def gotProtocol(p):
            print "PROTO", p
            print "CC", p.client_connection

        d = self.createSSHConnection()
        d.addCallback(gotProtocol)
        return d
#        channel = None
#        return channel
#        d.addCallback(gotProtocol)


    def createConnection(self, source_port, dest_port, service_parameters):

        d = self.getSSHChannel()
        return d




class JunOSConnection:

    def __init__(self, source_port, dest_port, service_parameters, channel):
        self.source_port = source_port
        self.dest_port = dest_port
        self.service_parameters
        self.channel = channel


    def stps(self):
        return self.service_parameters.source_stp, self.service_parameters.dest_stp


    def reserve(self):
        err = NotImplementedError('constructing..')
        return defer.fail(err)


    def provision(self):
        err = NotImplementedError('constructing..')


    def release(self):
        err = NotImplementedError('constructing..')


    def terminate(self):
        err = NotImplementedError('constructing..')


