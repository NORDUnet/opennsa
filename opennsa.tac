#!/usr/bin/env python # syntax highlightning

from twisted.application import internet, service

from opennsa import setup
from opennsa.proxies import dud


PORT = 4321

NETWORK_NAME = 'dudnetwork'



proxy = dud.DUDNSIProxy(NETWORK_NAME)

factory = setup.createFactory(NETWORK_NAME, proxy)



application = service.Application("OpenNSA")

internet.TCPServer(PORT, factory, interface='localhost').setServiceParent(application)

