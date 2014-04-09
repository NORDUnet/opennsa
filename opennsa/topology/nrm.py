"""
NRM topology parser.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2011-2012)
"""

import re
import StringIO

from opennsa import constants as cnt, nsa, error
from opennsa.topology import nml


LOG_SYSTEM = 'topology.nrm'


ETHERNET   = 'ethernet' # implied bidirectional

PORT_TYPES = [ ETHERNET ] # OpenNSA doesn't really do unidirectional at the moment

LABEL_TYPES = {
    'vlan'  : cnt.ETHERNET_VLAN
}


# format: network#port OR network#port-(in|out)
PORT_RX = re.compile('([^#]+)#([^\(]+)(?:\((.+?)\|(.+?)\))?')


class NRMSpecificationError(Exception):
    pass



class NRMPort(object):

    def __init__(self, port_type, name, remote_name, remote_in, remote_out, label, bandwidth, interface, authz):
        self.port_type      = port_type     # string
        self.name           = name          # string
        self.remote_name    = remote_name   # topology:port
        self.remote_in      = remote_in     # topology:port
        self.remote_out     = remote_out    # topology:port
        self.label          = label         # nsa.Label
        self.bandwidth      = bandwidth     # int
        self.interface      = interface     # string
        self.authz          = authz         # [ nsa.SecuritAttribte ]


    def isAuthorized(self, security_attributes):
        for port_sa in self.authz:
            if not any( [ port_sa.match(rsa) for rsa in security_attributes] ):
                return False
        return True



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

    if not ':' in label_spec:
        raise error.TopologyError('Invalid label description: %s' % label_spec)

    label_type_alias, label_range = label_spec.split(':', 1)
    try:
        label_type = LABEL_TYPES[label_type_alias]
    except KeyError:
        raise error.TopologyError('Label type %s does not map to proper label.' % label_type_alias)

    return nsa.Label(label_type, label_range) # range is parsed in nsa.Label



def createNMLTopology(nrm_ports, network_name):
    network_readable_name = network_name.split(':')[0]
    return createNMLNetwork(nrm_ports, network_name, network_readable_name)



def parsePortSpec(source):

    # Parse the entries like the following:

    ## type       name            remote                         label               bandwidth interface  authz
    #
    #ethernet     ps              -                              vlan:1780-1783      1000       em0        user=user@example.org
    #ethernet     netherlight     netherlight#nordunet-(in|out)  vlan:1780-1783      1000       em1        -
    #ethernet     uvalight        uvalight#nordunet-(in|out)     vlan:1780-1783      1000       em2        nsa=aruba.net:nsa

    # Line starting with # and blank lines should be ignored

    assert isinstance(source, file) or isinstance(source, StringIO.StringIO), 'Topology source must be file or StringIO instance'

    nrm_ports = []

    for line in source:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        tokens = [ t for t in line.split(' ') if t != '' ]
        if len(tokens) != 7:
            raise NRMSpecificationError('Invalid number of entries for entry: %s' % line)

        port_type, port_name, remote_spec, label_spec, bandwidth, interface, authz = tokens

        if not port_type in PORT_TYPES:
            raise error.TopologyError('Port type %s is not a valid port type' % port_type)

        remote_network, remote_port, in_suffix, out_suffix = _parseRemoteSpec(remote_spec)
        label = _parseLabelSpec(label_spec)

        try:
            bandwidth = int(bandwidth)
        except ValueError as e:
            raise NRMSpecificationError('Invalid bandwidth: %s' % str(e))

        if port_type == ETHERNET:
            if remote_network is None:
                remote_bd_port  = None
                remote_in       = None
                remote_out      = None
            else:
                if not in_suffix or not out_suffix:
                    raise NRMSpecificationError('Suffix not defined for bidirectional port %s' % port_name)
                remote_bd_port  = remote_network + ':' + remote_port
                remote_in       = remote_network + ':' + remote_port + in_suffix
                remote_out      = remote_network + ':' + remote_port + out_suffix
        else:
            raise AssertionError('do not know what to with port of type %s' % port_type)

        if authz == '-':
            authz_attributes = []
        else:
            authz_attributes = [ nsa.SecurityAttribute(*av.split('=',2)) for av in authz.split(',') ]

        nrm_ports.append( NRMPort(port_type, port_name, remote_bd_port, remote_in, remote_out, label, bandwidth, interface, authz_attributes) )

    return nrm_ports



# this could probably go another module, but for now it is here
def createNMLNetwork(nrm_ports, network_name, network_readable_name):

    inbound_ports       = []
    outbound_ports      = []
    bidirectional_ports = []

    for port in nrm_ports:

        assert port.port_type == ETHERNET, 'Sorry can only do ethernet ports for now'

        inbound_port_name   = port.name + '-in'
        outbound_port_name  = port.name + '-out'

        port_id             = network_name + ':' + port.name
        inbound_port_id     = network_name + ':' + inbound_port_name
        outbound_port_id    = network_name + ':' + outbound_port_name

        inbound_port        = nml.InternalPort(inbound_port_id,  inbound_port_name,  port.bandwidth, port.label, port.remote_out)
        outbound_port       = nml.InternalPort(outbound_port_id, outbound_port_name, port.bandwidth, port.label, port.remote_in)
        bidirectional_port  = nml.BidirectionalPort(port_id, port.name, inbound_port, outbound_port, port.remote_name)

        inbound_ports.append(inbound_port)
        outbound_ports.append(outbound_port)
        bidirectional_ports.append(bidirectional_port)

    return nml.Network(network_name, network_readable_name, inbound_ports, outbound_ports, bidirectional_ports)

