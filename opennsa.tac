#!/usr/bin/env python # syntax highlightning

from twisted.application import internet, service

from opennsa import setup
from opennsa.backends import dud


#TOPOFILE = 'topology_simple.json'
TOPOFILE = 'topology_simple_ws.json'

PORT = 9080

NETWORK_NAME = 'B'



proxy = dud.DUDNSIBackend(NETWORK_NAME)

factory = setup.createService(NETWORK_NAME, open(TOPOFILE), proxy, PORT)



application = service.Application("OpenNSA")

internet.TCPServer(PORT, factory, interface='localhost').setServiceParent(application)

