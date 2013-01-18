"""
OpenNSA NML topology model.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2011-2013)
"""

from opennsa import nsa, error


# Port orientations
INBOUND  = 'Inbound'
OUTBOUND = 'Outbound'

# Label types
ETHERNET = 'http://schemas.ogf.org/nml/2012/10/ethernet'
ETHERNET_VLAN = ETHERNET + '#vlan'



class Port:

    def __init__(self, name, orientation, labels, bandwidth, remote_network=None, remote_port=None):

        assert ':' not in name, 'Invalid port name, must not contain ":"'
        assert orientation in (INBOUND, OUTBOUND), 'Invalid port orientation: %s' % orientation
        assert (remote_network and remote_port) or not (remote_network and remote_port), 'Must specify remote network and port or none of them'

        self.name           = name              # String  ; Base name, no network name or uri prefix
        self.orientation    = orientation       # Must be INBOUND or OUTBOUND
        self.labels         = labels            # [ nsa.Label ]  ; can be empty
        self.bandwidth      = bandwidth         # Integer  ; in Mbps
        self.remote_network = remote_network    # String
        self.remote_port    = remote_port       # String


    def canMatchLabels(self, stp):
        if stp.labels is None and self.labels is None:
            return True
        else:
            return [ l.type_ for l in stp.labels ] == [ l.type_ for l in self.labels ]


    def canProvideBandwidth(self, desired_bandwidth):
        return desired_bandwidth <= self.bandwidth



class BidirectionalPort:

    def __init__(self, name, inbound_port, outbound_port):
        self.name = name
        self.orientation = nsa.BIDIRECTIONAL
        self.inbound_port  = inbound_port
        self.outbound_port = outbound_port


    def canMatchLabels(self, stp):
        return self.inbound_port.canMatchLabel(stp) and self.outbound_port.canMatchLabel(stp)



class Network:

    def __init__(self, name, ns_agent, ports, port_interface_map):

        # we should perhaps check for no ports with the same name, or build a dict

        self.name       = name      # String  ; just base name, no prefix or URI stuff
        self.nsa        = ns_agent  # nsa.NetworkServiceAgent
        self.ports      = ports     # [ Port | BidirectionalPort ]
        self.port_interface_map = port_interface_map # { port_name : interface }


    def getPort(self, port_name):
        for port in self.ports:
            if port.name == port_name:
                return port
        raise error.TopologyError('No port named %s for network %s' %(port_name, self.name))


    def getInterface(self, port_name):
        try:
            return self.port_interface_map[port_name]
        except KeyError:
            # we probably want to change the error type sometime
            raise error.TopologyError('No interface mapping for port %s' % port_name)


    def canSwapLabel(self, label_type):
        return self.label_type == ETHERNET_VLAN and self.name.statswith('urn:ogf:network:nordu.net:')



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


    def findPaths(self, source_stp, dest_stp, bandwidth):
        # sanity checks
        if source_stp.orientation is None:
            raise error.TopologyError('Cannot perform path finding, source stp has no orientation')
        if dest_stp.orientation is None:
            raise error.TopologyError('Cannot perform path finding, source stp has no orientation')
        # consider changing these to something like in (egrees, ingress), (ingress,egress), (bidirectional, bidirectional)
        if source_stp.orientation == nsa.BIDIRECTIONAL and dest_stp.orientation != nsa.BIDIRECTIONAL:
            raise error.TopologyError('Cannot connect bidirectional source with unidirectional destination')
        if dest_stp.orientation == nsa.BIDIRECTIONAL and source_stp.orientation != nsa.BIDIRECTIONAL:
            raise error.TopologyError('Cannot connect bidirectional destination with unidirectional source')
        if source_stp.orientation == dest_stp.orientation and source_stp.orientation != nsa.BIDIRECTIONAL:
            raise error.TopologyError('Cannot connect STPs of same unidirectional direction')

        source_network = self.getNetwork(source_stp.network)
        dest_network   = self.getNetwork(dest_stp.network)
        source_port    = source_network.getPort(source_stp.port)
        dest_port      = dest_network.getPort(dest_stp.port)

        if not source_port.canMatchLabels(source_stp.labels):
            raise error.TopologyError('Source port cannot match labels for source STP')
        if not dest_port.canMatchLabels(dest_stp.labels):
            raise error.TopologyError('Desitination port cannot match labels for destination STP')
        if not source_port.canProvideBandwidth(bandwidth):
            raise error.TopologyError('Source port cannot provide enough bandwidth (%i)' % bandwidth)
        if not dest_port.canProvideBandwidth(bandwidth):
            raise error.TopologyError('Destination port cannot provide enough bandwidth (%i)' % bandwidth)

        if source_stp.orientation == nsa.BIDIRECTIONAL and dest_stp.orientation == nsa.BIDIRECTIONAL:
            # bidirectional path finding, easy case first
            if source_stp.network == dest_stp.network:
                # while it possible to cross other network in order to connect to intra-network STPs
                # it is not something we really want to do in the real world
                if source_network.canSwapLabels():
                    link = nsa.Link(source_stp.network, source_stp.port, dest_stp.port,
                                    source_stp.orientation, dest_stp.orientation, source_stp.labels, dest_stp.labels)
                    return [ link ]
                else:
                    # in theory we could route to a network with label-swapping capability and route back
                    # but we don't support such crazyness (yet)
                    try:
                        is_labels = [ sl.intersect(dl) for sl, dl in zip(source_stp.labels, dest_stp.labels) ]
                        link = nsa.Link(source_stp.network, source_stp.port, dest_stp.port,
                                        source_stp.orientation, dest_stp.orientation, is_labels, is_labels)
                        return [ link ]
                    except nsa.EmptyLabelSet:
                        return [] # no path
            else:
                pass


        else:
            raise error.TopologyError('Unidirectional path-finding not implemented yet')

