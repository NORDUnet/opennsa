from twisted.internet import protocol
from twisted.application import internet, service

from opennsa import jsonrpc

PORT = 4321


def add(*args):
    return sum(args)



class JSONRPCFactory(protocol.Factory):

    protocol = jsonrpc.JSONRPCService

    def buildProtocol(self, addr):

        p = self.protocol()
        p.registerFunction('add', add)
        p.factory = self
        return p


factory = JSONRPCFactory()


application = service.Application("OpenNSA")

internet.TCPServer(PORT, factory, interface='localhost').setServiceParent(application)

