"""
NRM topology parser.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2011-2012)
"""

import re
import StringIO

from twisted.python import log

from opennsa import nsa, error
from opennsa.topology import nml


LOG_SYSTEM = 'topology.nrmparser'


BIDRECTIONAL_ETHERNET   = 'bi-ethernet'
UNIDIRECTIONAL_ETHERNET = 'uni-ethernet'

PORT_TYPES = [ BIDRECTIONAL_ETHERNET, UNIDIRECTIONAL_ETHERNET ]

LABEL_TYPES = {
    'vlan'  : nml.ETHERNET_VLAN
}



class NRMEntry:

    def __init__(self, port_type, port_name, remote_port, labels, interface):
        # port_type     : string
        # port_name     : string
        # remote_port   : (string, string, string, string)
        # labels        : [ nsa.Label ]
        # interface     : string

        self.port_type  = port_type
        self.port_name  = port_name
        self.remote_port = remote_port
        self.labels     = labels
        self.interface  = interface


    def __str__(self):
        return '<NRMEntry: %s, %s, %s, %s, %s>' % (self.port_type, self.port_name, self.remote_port, self.labels, self.interface)



def parseTopologySpec(source):

    # Parse the entries like the following:

    ## type          name            remote                          labels              interface
    #
    #bi-ethernet     ps              -                               vlan:1780-1783      em0
    #bi-ethernet     netherlight     netherlight:nordu-netherlight   vlan:1780-1783      em1
    #bi-ethernet     uvalight        uvalight:uvalight               vlan:1780-1783      em2

    # Line starting with # and blank lines should be ignored

    assert isinstance(source, file) or isinstance(source, StringIO.StringIO), 'Topology source must be file or StringIO instance'

    TOPO_RX = re.compile('''(.+?)\s+(.+?)\s+(.+?)\s+(.+?)\s+(.+)''')
    PORT_RX = re.compile("(.+?)\((.+?)\|(.+?)\)@(.+?)")
    entries = []

    for line in source:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        match = TOPO_RX.match(line)
        if not match:
            print "No match for entry: ", line # parsing is typically done on startup, so print is probably ok

        else:
            port_type, port_name, remote_port, label_spec, interface = match.groups()

            if not port_type in PORT_TYPES:
                raise error.TopologyError('Port type %s is not a valid port type' % port_type)

            if remote_port == '-':
                remote_port = None
            else:
                match = PORT_RX.match(remote_port)
                if not match:
                    raise error.TopologyError('Remote %s is not valid: either "-" or "base(-insuffix|-outsuffix)@domain"' % remote_port)
                remote_port = match.groups()

            labels = []

            for l_entry in label_spec.split(','):
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


            if interface.startswith('"') and interface.endswith('"'):
                interface = interface[1:-1]

            ne = NRMEntry(port_type, port_name, remote_port, labels, interface)
            entries.append(ne)

    # check for no entries?

    return entries



def createNetwork(network_name, ns_agent, nrm_entries):

    # could consider merging this one with the parser

    port_interface_map = {}
    ports = []

    bandwidth = 1000 # until we get in the NRM spec

    for ne in nrm_entries:

        if ne.port_type == BIDRECTIONAL_ETHERNET:
            base_name, in_suffix, out_suffix, domain = ne.remote_port
            inbound_port  = nml.Port(ne.port_name + '-in',  nml.INBOUND,  ne.labels, bandwidth, (domain, base_name+out_suffix))
            outbound_port = nml.Port(ne.port_name + '-out', nml.OUTBOUND, ne.labels, bandwidth, (domain, base_name+in_suffix))
            port = nml.BidirectionalPort(inbound_port, outbound_port)

            ports += [ inbound_port, outbound_port, port ]

            port_interface_map[ne.port_name] = ne.interface

        elif ne.port_type == UNIDIRECTIONAL_ETHERNET:

            raise NotImplementedError('Unidirectional ethernet ports not supported')

        else:
            raise error.TopologyError('Invalid port type: %s' % port_type)

    network = nml.Network(network_name, ns_agent, ports, port_interface_map)

    return network

