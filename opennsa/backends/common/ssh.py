"""
Basic SSH connectivity.
"""

from twisted.python import log
from twisted.internet import defer, protocol, reactor, endpoints
from twisted.conch import error as concherror
from twisted.conch.ssh import transport, keys, userauth, connection, channel


LOG_SYSTEM = 'opennsa.SSH'



class SSHClientTransport(transport.SSHClientTransport):

    def __init__(self, fingerprints):
        self.fingerprints = fingerprints
        self.connection_secure_d = defer.Deferred()


    def verifyHostKey(self, public_key, fingerprint):
        if fingerprint in self.fingerprints:
            return defer.succeed(1)
        else:
            return defer.fail(concherror.ConchError('Fingerprint not accepted'))


    def connectionSecure(self):
        self.connection_secure_d.callback(self)



class SSHClientFactory(protocol.ClientFactory):

    protocol = SSHClientTransport

    def __init__(self, fingerprints):
        # ClientFactory has no __init__ method
        self.fingerprints = fingerprints # this is just a passthrough to the transport protocol
        self.stopped = False


    def buildProtocol(self, addr):
        p = self.protocol(self.fingerprints)
        p.factory = self
        return p


    def stopFactory(self):
        log.msg('SSH client factory stopped (new connection must be created).', system=LOG_SYSTEM)
        self.stopped = True



class KeyUserAuthClient(userauth.SSHUserAuthClient):

    def __init__(self, user, connection, public_key_path, private_key_path):
        userauth.SSHUserAuthClient.__init__(self, user, connection)
        self.public_key_path  = public_key_path
        self.private_key_path = private_key_path

    def getPassword(self, prompt=None):
        return # this says we won't do password authentication

    def getPublicKey(self):
        return keys.Key.fromFile(self.public_key_path)

    def getPrivateKey(self):
        return defer.succeed( keys.Key.fromFile(self.private_key_path) )



class PasswordUserAuthClient(userauth.SSHUserAuthClient):

    def __init__(self, user, connection, password):
        userauth.SSHUserAuthClient.__init__(self, user, connection)
        self.password = password

    def getPassword(self, prompt=None):
        return defer.succeed( self.password )



class SSHConnection(connection.SSHConnection):

    def __init__(self):
        connection.SSHConnection.__init__(self)
        self.ssh_connection_established_d = defer.Deferred()

    def serviceStarted(self):
        self.ssh_connection_established_d.callback(self)



class SSHChannel(channel.SSHChannel):

    name = 'session'

    def __init__(self, localWindow=0, localMaxPacket=0, remoteWindow=0, remoteMaxPacket=0, conn=None, data=None, avatar=None):
        channel.SSHChannel.__init__(self, localWindow, localMaxPacket, remoteWindow, remoteMaxPacket, conn, data, avatar)
        self.channel_open = defer.Deferred()


    def channelOpen(self, data):
        self.channel_open.callback(self)
        log.msg('SSH channel open.', debug=True, system=LOG_SYSTEM)


    def request_exit_status(self, data):
        if data and len(data) != 4:
            log.msg('Exit status data: %s' % data, system=LOG_SYSTEM)


    def sendEOF(self, passthru=None):
        self.conn.sendEOF(self) # should this be on self?
        return passthru


    def closeIt(self, passthru=None):
        self.loseConnection()
        return passthru


    def dataReceived(self, data):
        raise NotImplementedError('SSHChannel.dataReceived must be overwritten in sub-class')



class SSHConnectionCreator:

    def __init__(self, host, port, fingerprints, username, public_key_path=None, private_key_path=None, password=None):
        self.host = host
        self.port = port
        self.fingerprints     = fingerprints
        self.username         = username
        self.public_key_path  = public_key_path
        self.private_key_path = private_key_path
        self.password         = password


    def createTCPConnection(self):
        # set up base connection and verify host
        def hostVerified(client, proto):
            return proto

        def gotProtocol(proto):
            proto.connection_secure_d.addCallback(hostVerified, proto)
            self.proto = proto
            return proto.connection_secure_d

        log.msg('Creating new TCP connection for SSH connection.', debug=True, system=LOG_SYSTEM)
        factory = SSHClientFactory(self.fingerprints)
        point = endpoints.TCP4ClientEndpoint(reactor, self.host, self.port)
        d = point.connect(factory)
        d.addCallback(gotProtocol)
        return d


    def getSSHConnection(self):
        # this should really be called createSSHConnection, but previously connecting caching was done here
        # however that is not put in the backend itself, where it fits much better

        def gotTCPConnection(proto):
            ssh_connection = SSHConnection()
            if self.public_key_path and self.private_key_path:
                proto.requestService(KeyUserAuthClient(self.username, ssh_connection, self.public_key_path, self.private_key_path))
            elif self.password:
                proto.requestService(PasswordUserAuthClient(self.username, ssh_connection, self.password))
            else:
                raise AssertionError('No ssh keys or password supplied')

            return ssh_connection.ssh_connection_established_d

        d = self.createTCPConnection()
        d.addCallback(gotTCPConnection)
        return d

