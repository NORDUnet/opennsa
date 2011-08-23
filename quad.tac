#!/usr/bin/env python # syntax highlightning

from twisted.application import internet, service

from opennsa import setup
from opennsa.backends import dud


TOPOFILE = 'nsi_interop_quad.owl'


SERVICE_CONFIG = ( ('Aruba', 9080), ('Bonaire', 9081), ('Curacao', 9082), ('Dominica', 9083) )


application = service.Application("OpenNSA")

for network_name, port in SERVICE_CONFIG:

    proxy = dud.DUDNSIBackend(network_name)
    factory = setup.createService(network_name, open(TOPOFILE), proxy, port)
    internet.TCPServer(port, factory, interface='localhost').setServiceParent(application)

