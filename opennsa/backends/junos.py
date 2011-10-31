"""
OpenNSA JunOS backend.
"""


# Stuff to get from config:

JUNOS_HOST              = 'cph.dcn.nordu.net'
JUNOS_HOST_PORT         = 22
JUNOS_HOST_FINGERPRINT  = 'd8:43:73:ee:a4:87:87:36:3f:c4:e5:3e:7c:d9:8b:d7'

USERNAME    = 'opennsa'
PUBLIC_KEY_PATH         = '/home/opennsa/.ssh/id_rsa'
PRIVATE_KEY_PATH        = '/home/opennsa/.ssh/id_rsa.pub'

#PUBLIC_KEY = open(PUBLIC_KEY_PATH).read()
#PRIVATE_KEY = open(PRIVATE_KEY_PATH).read()



from twisted.internet import defer, protocol, reactor

from twisted.conch import error
from twisted.conch.ssh import common, transport, keys, userauth, connection, channel



class ClientTransport(transport.SSHClientTransport):

    def __init__(self): #, host_fingerprint):
        self.host_fingerprint = JUNOS_HOST_FINGERPRINT

    def verifyHostKey(self, public_key, fingerprint):
        if fingerprint != self.host_fingerprint:
            return defer.fail(error.ConchError('bad key'))
        else:
            return defer.succeed(1)

    def connectionSecure(self):
        self.requestService(ClientUserAuth('user', ClientConnection(), PUBLIC_KEY_PATH, PRIVATE_KEY_PATH))



class ClientUserAuth(userauth.SSHUserAuthClient):

    def __init__(self, user, connection, public_key_path, private_key_path):
        userauth.SSHUserAuthClient.__init__(self, user, connection)
        self.public_key_path    = public_key_path
        self.private_key_path   = private_key_path

    def getPassword(self, prompt = None):
        return # this says we won't do password authentication

    def getPublicKey(self):
        return keys.Key.fromFile(self.public_key_path).blob()

    def getPrivateKey(self):
        return defer.succeed(keys.Key.fromFile(self.private_key_path).keyObject)



class ClientConnection(connection.SSHConnection):

    def serviceStarted(self):
        self.openChannel(ConfigureChannel(conn = self))



class ConfigureChannel(channel.SSHChannel):

    name = 'session'

    def channelOpen(self, data):
        #d = self.conn.sendRequest(self, 'exec', common.NS('configure'), wantReply = 1)
        pass # don't do anything now, wait until we get a request


    def ping(self):
        d = self.conn.sendRequest(self, 'exec', common.NS('ping orval.grid.aau.dk count 2'), wantReply = 1)
        d.addCallback(self.sendEOF)
        d.addCallback(self.closeIt)
        return d
#        d.addCallback(self._cbSendRequest)
#        self.catData = ''

    def sendEOF(self, passthru):
        self.conn.sendEOF(self)
        return passthru


    def closeIt(self, passthru):
        self.conn.loseConnection()
        return passthru

#    def _cbSendRequest(self, ignored):
#        self.write('This data will be echoed back to us by "cat."\r\n')
#        self.conn.sendEOF(self)
#        self.loseConnection()

    def dataReceived(self, data):
        print "DATA"
        #self.catData += data

    def closed(self):
        print "SSH Connection closed"
#        print 'We got this from "cat":', self.catData








class JunOSBackend:

    def __init__(self, network_name):
        self.network_name = network_name


    def createRouterConnection(self):

        factory = protocol.ClientFactory()
        factory.protocol = ClientTransport
        reactor.connectTCP(JUNOS_HOST, JUNOS_HOST_PORT, factory)
        return factory


    def createConnection(self, source_port, dest_port, service_parameters):

        self.createRouterConnection()




class JunOSConnection:

    def __init__(self, source_port, dest_port, service_parameters, channel):
        self.source_port = source_port
        self.dest_port = dest_port
        self.service_parameters
        self.channel = channel


    def stps(self):
        return self.service_parameters.source_stp, self.service_parameters.dest_stp


    def reserve(self):
        raise NotImplemented('constructing..')


    def provision(self):
        raise NotImplemented('constructing..')


    def release(self):
        raise NotImplemented('constructing..')


    def terminate(self):
        raise NotImplemented('constructing..')


