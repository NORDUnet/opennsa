"""
NRM topology parser.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2011-2012)
"""

import re
import StringIO

from twisted.python import log

from opennsa import constants as cnt, nsa, error
from opennsa.topology import nml


LOG_SYSTEM = 'topology.nrmparser'


BIDRECTIONAL_ETHERNET   = 'bi-ethernet'
UNIDIRECTIONAL_ETHERNET = 'uni-ethernet'

PORT_TYPES = [ BIDRECTIONAL_ETHERNET, UNIDIRECTIONAL_ETHERNET ]

LABEL_TYPES = {
    'vlan'  : cnt.ETHERNET_VLAN
}


TOPO_RX = re.compile('(.+?)\s+(.+?)\s+(.+?)\s+(.+?)\s+(.+?)\s+(.+)')
# format: network#port OR network#port-(in|out)
PORT_RX = re.compile('([^#]+)#([^\(]+)(?:\((.+?)\|(.+?)\))?')


class NRMSpecificationError(Exception):
    pass



def _parseRemoteSpec(remote_spec):
    # return 4-tuple: network, port, in suffix, out suffix
    if remote_spec == '-':
        return None, None, None, None
    else:
        match = PORT_RX.match(remote_spec)
        if not match:
            raise error.TopologyError('Remote %s is not valid: either "-" or "domain#base(-insuffix|-outsuffix)?"' % remote_spec)
        return match.groups()


def _parseLabelSpec(label_spec):
    labels = []
    for l_entry in label_spec.split('|'):
        if not ':' in l_entry:
            raise error.TopologyError('Invalid label description: %s' % l_entry)

        label_type_alias, label_range = l_entry.split(':', 1)
        try:
            label_type = LABEL_TYPES[label_type_alias]
        except KeyError:
            raise error.TopologyError('Label type %s does not map to proper label.' % label_type_alias)

        if label_type in [ label.type_ for label in labels ]:
            raise error.TopologyError('Multiple labels for type %s' % label_type)

        labels.append( nsa.Label(label_type, label_range) ) # range is parsed in nsa.Label
    return labels


def parseTopologySpec(source, base_name):

    inbound_ports, outbound_ports, bidirectional_ports, port_interface_map = parsePortSpec(source, base_name)

    network_name = base_name + ':topology'
    network = nml.Network(network_name, base_name, inbound_ports, outbound_ports, bidirectional_ports)
    return network, port_interface_map


def parsePortSpec(source, network_name):

    # Parse the entries like the following:

    ## type          name            remote                         labels              interface
    #
    #bi-ethernet     ps              -                              vlan:1780-1783      em0
    #bi-ethernet     netherlight     netherlight#nordunet-(in|out)  vlan:1780-1783      em1
    #bi-ethernet     uvalight        uvalight#nordunet-(in|out)     vlan:1780-1783      em2

    # Line starting with # and blank lines should be ignored

    assert isinstance(source, file) or isinstance(source, StringIO.StringIO), 'Topology source must be file or StringIO instance'

    port_interface_map = {}
    inbound_ports       = []
    outbound_ports      = []
    bidirectional_ports = []

    for line in source:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        match = TOPO_RX.match(line)
        if not match:
            raise NRMSpecificationError('No match for entry: %s' % line)

        port_type, port_name, remote_spec, label_spec, bandwidth, interface = match.groups()

        if not port_type in PORT_TYPES:
            raise error.TopologyError('Port type %s is not a valid port type' % port_type)

        remote_network, remote_port, in_suffix, out_suffix = _parseRemoteSpec(remote_spec)
        labels = _parseLabelSpec(label_spec)

        try:
            bandwidth = int(bandwidth)
        except ValueError as e:
            raise NRMSpecificationError('Invalid bandwidth: %s' % str(e))

        if interface.startswith('"') and interface.endswith('"'):
            interface = interface[1:-1]

        if port_type == BIDRECTIONAL_ETHERNET:
            if remote_network is None:
                remote_in  = None
                remote_out = None
            else:
                if not in_suffix or not out_suffix:
                    raise NRMSpecificationError('Suffix not defined for bidirectional port %s' % port_name)
                remote_in  = remote_port + in_suffix
                remote_out = remote_port + out_suffix

            inbound_port_name   = port_name + '-in'
            outbound_port_name  = port_name + '-out'

            port_id             = network_name + ':' + port_name
            inbound_port_id     = network_name + ':' + inbound_port_name
            outbound_port_id    = network_name + ':' + outbound_port_name

            inbound_port        = nml.InternalPort(inbound_port_id,  inbound_port_name,  bandwidth, labels, remote_network, remote_out)
            outbound_port       = nml.InternalPort(outbound_port_id, outbound_port_name, bandwidth, labels, remote_network, remote_in)
            bidirectional_port  = nml.BidirectionalPort(port_id, port_name, inbound_port, outbound_port)

            inbound_ports.append(inbound_port)
            outbound_ports.append(outbound_port)
            bidirectional_ports.append(bidirectional_port)

            port_interface_map[port_id] = interface

        elif port_type == UNIDIRECTIONAL_ETHERNET:
            raise NotImplementedError('Unidirectional ethernet ports not implemented yet')

    return inbound_ports, outbound_ports, bidirectional_ports, port_interface_map

