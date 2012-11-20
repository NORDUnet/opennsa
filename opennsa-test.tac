#!/usr/bin/env python # syntax highlightning

import os, sys

from twisted.python import log
from twisted.python.log import ILogObserver
from twisted.application import internet, service

from opennsa import setup, registry, logging, nsiservice
from opennsa.backends import dud
from opennsa.topology import gole
from opennsa.protocols import nsi1


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

topo, _ = gole.parseTopology( [ open(TOPOLOGY) ], open(MAPPING))

for network, port in SERVICES:

    backend = dud.DUDNSIBackend(network)
    factory = nsi1.createService(network, backend, topo, HOST, port, WSDL_DIR)

    internet.TCPServer(port, factory, interface='localhost').setServiceParent(application)

