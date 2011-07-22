#!/usr/bin/env python # syntax highlightning

from twisted.application import internet, service

from opennsa import setup
from opennsa.backends import dud


TOPOFILE = 'topology_simple.json'

PORT = 4321

NETWORK_NAME = 'B'



proxy = dud.DUDNSIBackend(NETWORK_NAME)

factory = setup.createFactory(NETWORK_NAME, open(TOPOFILE), proxy)



application = service.Application("OpenNSA")

internet.TCPServer(PORT, factory, interface='localhost').setServiceParent(application)

