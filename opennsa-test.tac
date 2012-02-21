#!/usr/bin/env python # syntax highlightning

import os, sys

from twisted.python import log
from twisted.python.log import ILogObserver
from twisted.application import internet, service

from opennsa import setup, registry, logging
from opennsa.backends import dud


DEBUG = False
PROFILE = False

TOPOLOGY = 'test-topology.owl'
MAPPING  = 'test-mapping.nrm'

HOST = 'localhost'

SERVICES = [ ('Aruba', 9080), ('Bonaire', 9081), ('Curacao',9082) ]

WSDL_DIR = os.path.join(os.getcwd(), 'wsdl')

## Log messages before "real" logging infrastructure comes up
#earlyObserver = logging.EarlyObserver()
#log.startLoggingWithObserver(earlyObserver.emit, setStdout=0)
#log.defaultObserver = earlyObserver # This will make the log system plug it out when the real logging starts

logObserver = logging.DebugLogObserver(sys.stdout, DEBUG, PROFILE)

application = service.Application("OpenNSA")
application.setComponent(ILogObserver, logObserver.emit)

for network, port in SERVICES:

    backend = dud.DUDNSIBackend(network)
    es = registry.ServiceRegistry()
    factory = setup.createService(network, [ open(TOPOLOGY) ], backend, es, HOST, port, WSDL_DIR, nrm_map_source=open(MAPPING) )

    internet.TCPServer(port, factory, interface='localhost').setServiceParent(application)

