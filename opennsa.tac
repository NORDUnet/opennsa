#!/usr/bin/env python # syntax highlightning

import os, sys

from twisted.python.log import ILogObserver
from twisted.application import internet, service

from opennsa import setup, logging
from opennsa.backends import dud


DEBUG = False

HOST = 'localhost'
PORT = 9080

TOPOFILE = 'local-topo.owl'
WSDL_DIR = os.path.join(os.getcwd(), 'wsdl')
NETWORK_NAME = 'Aruba'


backend = dud.DUDNSIBackend(NETWORK_NAME)
factory = setup.createService(NETWORK_NAME, open(TOPOFILE), backend, HOST, PORT, WSDL_DIR)

application = service.Application("OpenNSA")
application.setComponent(ILogObserver, logging.DebugLogObserver(sys.stdout, DEBUG).emit)

internet.TCPServer(PORT, factory, interface='localhost').setServiceParent(application)

