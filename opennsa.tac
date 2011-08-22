#!/usr/bin/env python # syntax highlightning

from twisted.application import internet, service

from opennsa import setup
from opennsa.backends import dud


TOPOFILE = 'nsi_interop_deuce.owl'

PORT = 9080

NETWORK_NAME = 'Aruba'



proxy = dud.DUDNSIBackend(NETWORK_NAME)

factory = setup.createService(NETWORK_NAME, open(TOPOFILE), proxy, PORT)



application = service.Application("OpenNSA")

internet.TCPServer(PORT, factory, interface='localhost').setServiceParent(application)

