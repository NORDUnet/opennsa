"""
OpenNSA NML topology model.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2011-2013)
"""

from opennsa import error


# Port orientations
INBOUND  = 'Inbound'
OUTBOUND = 'Outbound'

# Label types
ETHERNET = 'http://schemas.ogf.org/nml/2012/10/ethernet'
ETHERNET_VLAN = ETHERNET + '#vlan'



class Port:

    def __init__(self, name, orientation, labels, bandwidth, alias=None):

        assert ':' not in name, 'Invalid port name, must not contain ":"'
        assert orientation in (INBOUND, OUTBOUND), 'Invalid port orientation: %s' % orientation

        self.name        = name         # String  ; Base name, no network name or uri prefix
        self.orientation = orientation  # Must be INBOUND or OUTBOUND
        self.labels      = labels       # [ nsa.Label ]  ; can be empty
        self.bandwidth   = bandwidth    # Integer  ; in Mbps
        self.alias       = alias        # None | (network, port)  ; port it connects to



class BidirectionalPort:

    def __init__(self, inbound_port, outbound_port):

        self.inbound_port  = inbound_port
        self.outbound_port = outbound_port



class Network:

    def __init__(self, name, ns_agent, ports, port_interface_map):

        # we should perhaps check for no ports with the same name, or build a dict

        self.name       = name      # String  ; just base name, no prefix or URI stuff
        self.nsa        = ns_agent  # nsa.NetworkServiceAgent
        self.ports      = ports     # [ Port | BidirectionalPort ]
        self.port_interface_map = port_interface_map # { port_name : interface }


    def getInterface(self, port_name):
        try:
            return self.port_interface_map[port_name]
        except KeyError:
            # we probably want to change the error type sometime
            raise error.TopologyError('No interface mapping for port %s' % port_name)



class Topology:

    def __init__(self):
        self.networks = []


    def addNetwork(self, network):
        if network.name in [ n.name for n in self.networks ]:
            raise error.TopologyError('Network name must be unique (name: %s)' % network.name)

        self.networks.append(network)


    def getNetwork(self, network_name):
        for network in self.networks:
            if network.name == network_name:
                return network

        raise error.TopologyError('No network named %s' % network_name)

