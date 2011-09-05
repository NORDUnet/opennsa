#!/usr/bin/env python # syntax highlightning

from twisted.application import internet, service

from opennsa import setup
from opennsa.backends import dud


TOPOFILE = 'Rio-Inter-Domain-Topo-Ring-v1.1b.owl'

NETWORK = 'Aruba'
PORT = 9080

proxy = dud.DUDNSIBackend(NETWORK)
factory = setup.createService(NETWORK, open(TOPOFILE), proxy, PORT)

application = service.Application("OpenNSA")
internet.TCPServer(PORT, factory, interface='localhost').setServiceParent(application)

