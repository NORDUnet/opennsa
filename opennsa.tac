#!/usr/bin/env python # syntax highlightning

import sys

from twisted.python.log import ILogObserver
from twisted.application import internet, service

from opennsa import setup, logging
from opennsa.backends import dud


TOPOFILE = 'local-topo.owl'

NETWORK_NAME = 'Aruba'
PORT = 9080

DEBUG = False


proxy = dud.DUDNSIBackend(NETWORK_NAME)
factory = setup.createService(NETWORK_NAME, open(TOPOFILE), proxy, PORT)

application = service.Application("OpenNSA")
application.setComponent(ILogObserver, logging.DebugLogObserver(sys.stdout, DEBUG).emit)

internet.TCPServer(PORT, factory, interface='localhost').setServiceParent(application)

