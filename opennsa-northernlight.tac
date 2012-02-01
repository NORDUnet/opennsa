#!/usr/bin/env python # syntax highlightning

import os, sys

from twisted.python.log import ILogObserver
from twisted.application import internet, service

from opennsa import setup, logging
from opennsa.backends import junos


DEBUG = True
TLS = True

HOST = 'orval.grid.aau.dk'
TCP_PORT = 9080
TLS_PORT = 9443

PORT = TLS_PORT if TLS else TCP_PORT

TOPOFILE = 'AutoGOLE-Topo-2012-01-25.owl'
WSDL_DIR = os.path.join(os.getcwd(), 'wsdl')
NETWORK_NAME = 'northernlight.ets'

ctx_factory = None
if TLS:
    from opennsa import ctxfactory
    ctx_factory = ctxfactory.ContextFactory('/etc/grid-security/hostkey.pem', '/etc/grid-security/hostcert.pem', '/etc/grid-security/certificates', False)

backend = junos.JunOSBackend(NETWORK_NAME)
factory = setup.createService(NETWORK_NAME, open(TOPOFILE), backend, HOST, PORT, WSDL_DIR, ctx_factory)

application = service.Application("OpenNSA")
application.setComponent(ILogObserver, logging.DebugLogObserver(sys.stdout, DEBUG).emit)

if TLS:
    internet.SSLServer(PORT, factory, ctx_factory).setServiceParent(application)
else:
    internet.TCPServer(PORT, factory).setServiceParent(application)

