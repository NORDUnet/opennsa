#!/usr/bin/env python # syntax highlightning

import json, urlparse

from twisted.application import internet, service

from opennsa import setup
from opennsa.backends import dud


TOPOFILE = 'topology_simple.json'

top = json.load(open(TOPOFILE))

networks = {}

for network, info in top.items():
    hostport = urlparse.urlparse(info['address']).netloc
    port = int(hostport.split(':',2)[1])

    networks[network] = port



application = service.Application("OpenNSA")


for network_name, port in networks.items():

    proxy = dud.DUDNSIBackend(network_name)
    factory = setup.createFactory(network_name, open(TOPOFILE), proxy)

    internet.TCPServer(port, factory, interface='localhost').setServiceParent(application)

