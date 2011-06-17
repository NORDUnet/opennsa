#!/usr/bin/env python # syntax highlightning

from twisted.internet import protocol
from twisted.application import internet, service

from opennsa import jsonrpc, nsirouter
from opennsa.proxies import dud

PORT = 4321

NETWORK_NAME = 'dudnetwork'

dud_proxy = dud.DUDNSIProxy(NETWORK_NAME)
nsi_router  = nsirouter.NSIRouterAdaptor(NETWORK_NAME, dud_proxy)

class OpenNSAJSONRPCFactory(protocol.Factory):

    protocol = jsonrpc.JSONRPCService

    def buildProtocol(self, addr):

        p = self.protocol()
        p.factory = self
        jsonrpc.JSONRPCNSIServiceAdaptor(p, nsi_router)
        return p



factory = OpenNSAJSONRPCFactory()

application = service.Application("OpenNSA")

internet.TCPServer(PORT, factory, interface='localhost').setServiceParent(application)

