#!/usr/bin/env python # syntax highlightning

import os, sys, socket

from twisted.python.log import ILogObserver
from twisted.application import internet, service

from opennsa import setup, logging
from opennsa.backends import junos


DEBUG = True

HOST = 'orval.grid.aau.dk'
PORT = 9080

TOPOFILE = 'FIA-Topo-v1.4c.owl'
WSDL_DIR = os.path.join(os.getcwd(), 'wsdl')
NETWORK_NAME = 'northernlight.ets'


backend = junos.JunOSBackend(NETWORK_NAME)
factory = setup.createService(NETWORK_NAME, open(TOPOFILE), backend, HOST, PORT, WSDL_DIR)

application = service.Application("OpenNSA")
application.setComponent(ILogObserver, logging.DebugLogObserver(sys.stdout, DEBUG).emit)

internet.TCPServer(PORT, factory).setServiceParent(application)

