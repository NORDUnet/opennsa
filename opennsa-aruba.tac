#!/usr/bin/env python # syntax highlightning

import sys

from twisted.python.log import ILogObserver
from twisted.application import internet, service

from opennsa import setup, logging
from opennsa.backends import dud


TOPOFILE = 'Rio-Inter-Domain-Topo-Ring-v1.1h.owl'

NETWORK_NAME = 'Aruba'
PORT = 9080


proxy = dud.DUDNSIBackend(NETWORK_NAME)
factory = setup.createService(NETWORK_NAME, open(TOPOFILE), proxy, PORT)

application = service.Application("OpenNSA")
application.setComponent(ILogObserver, logging.DebugLogObserver(sys.stdout, True).emit)

internet.TCPServer(PORT, factory).setServiceParent(application)

