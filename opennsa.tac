#!/usr/bin/env python # syntax highlightning

from twisted.application import internet, service

from opennsa import setup
from opennsa.proxies import dud


TOPOFILE = 'topology_simple.json'

PORT = 4321

NETWORK_NAME = 'B'



proxy = dud.DUDNSIProxy(NETWORK_NAME)

factory = setup.createFactory(NETWORK_NAME, TOPOFILE, proxy)



application = service.Application("OpenNSA")

internet.TCPServer(PORT, factory, interface='localhost').setServiceParent(application)

