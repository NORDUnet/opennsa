"""
OpenNSA NML topology model.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2011-2013)
"""

import itertools
import datetime

from twisted.python import log

from opennsa import constants as cnt, nsa, error


LOG_SYSTEM = 'opennsa.topology'

INGRESS = 'ingress'
EGRESS  = 'egress'



class Port(object):

    def __init__(self, id_, name, label, remote_port=None):

        assert not id_.startswith('urn:'), 'URNs are not used in core OpenNSA NML (id: %s)' % id_
        assert ':' not in name, 'Invalid port name %s, must not contain ":"' % name
        if label is not None:
            assert type(label) is nsa.Label, 'label must be nsa.Label or None, not type(%s)' % str(type(label))

        self.id_            = id_               # The URN of the port
        self.name           = name              # String  ; Base name, no network name or uri prefix
        self._label         = label             # nsa.Label ; can be None
        self.remote_port    = remote_port       # String


    def canMatchLabel(self, label):
        return nsa.Label.canMatch(self, label)


    def isBidirectional(self):
        return False


    def label(self):
        return self._label


    def hasRemote(self):
        return self.remote_port != None


    def __repr__(self):
        return '<Port %s (%s) # %s -> %s>' % (self.id_, self.name, self._label, self.remote_port)



class InternalPort(Port):
    """
    Same as Port, but also has a bandwidth, so the pathfinder can probe for bandwidth.
    """
    def __init__(self, id_, name, bandwidth, label, remote_port=None):
        super(InternalPort, self).__init__(id_, name, label, remote_port)
        self.bandwidth = bandwidth


    def canProvideBandwidth(self, desired_bandwidth):
        return desired_bandwidth <= self.bandwidth


    def __repr__(self):
        return '<InternalPort %s (%s) # %s : %i -> %s>' % (self.id_, self.name, self._label, self.bandwidth, self.remote_port)



class BidirectionalPort(object):

    def __init__(self, id_, name, inbound_port, outbound_port, remote_port=None):
        assert type(id_) is str, 'Port id must be a string'
        assert type(name) is str, 'Port name must be a string'
        assert isinstance(inbound_port, Port), 'Inbound port must be a <Port>'
        assert isinstance(outbound_port, Port), 'Outbound port must be a <Port>'
        assert inbound_port.label().type_ == outbound_port.label().type_, 'Port labels must match each other'
        assert not id_.startswith('urn:'), 'URNs are not used in core OpenNSA NML (id: %s)' % id_

        self.id_ = id_
        self.name = name
        self.inbound_port  = inbound_port
        self.outbound_port = outbound_port
        self.remote_port   = remote_port # hack on!


    def isBidirectional(self):
        return True


    def label(self):
        if self.inbound_port.label() and self.outbound_port.label():
            return self.inbound_port.label().intersect(self.outbound_port.label())
        else:
            return None


    def canMatchLabel(self, label):
        return self.inbound_port.canMatchLabel(label) and self.outbound_port.canMatchLabel(label)


    def hasRemote(self):
        return self.inbound_port.hasRemote() and self.outbound_port.hasRemote()


    def canProvideBandwidth(self, desired_bandwidth):
        return self.inbound_port.canProvideBandwidth(desired_bandwidth) and self.outbound_port.canProvideBandwidth(desired_bandwidth)

    def __repr__(self):
        return '<BidirectionalPort %s (%s) : %s/%s>' % (self.id_, self.name, self.inbound_port.name, self.outbound_port.name)



class Network(object):

    def __init__(self, id_, name, inbound_ports, outbound_ports, bidirectional_ports, version=None):

        assert type(id_) is str, 'Network id must be a string'
        assert type(name) is str, 'Network name must be a string'
        assert type(inbound_ports) is list, 'Inbound ports must be a list'
        assert type(outbound_ports) is list, 'Outbound network ports must be a list'
        assert type(bidirectional_ports) is list, 'Bidirectional network ports must be a list'
        assert not id_.startswith('urn:'), 'URNs are not used in core OpenNSA NML (id: %s)' % id_

        # we should perhaps check that no ports has the same name

        self.id_                 = id_           # String  ; the urn of the network topology
        self.name                = name          # String  ; just base name, no prefix or URI stuff
        self.inbound_ports       = inbound_ports or []
        self.outbound_ports      = outbound_ports or []
        self.bidirectional_ports = bidirectional_ports or []
        self.version             = version or datetime.datetime.utcnow().replace(microsecond=0)


    def getPort(self, port_id):
        for port in itertools.chain(self.inbound_ports, self.outbound_ports, self.bidirectional_ports):
            if port.id_ == port_id:
                return port
        # better error message
        ports = [ p.id_ for p in list(itertools.chain(self.inbound_ports, self.outbound_ports, self.bidirectional_ports)) ]
        raise error.STPUnavailableError('No port named %s for network %s (ports: %s)' %(port_id, self.id_, str(ports)))


    def findPorts(self, bidirectionality, label=None, exclude=None):
        matching_ports = []
        for port in itertools.chain(self.inbound_ports, self.outbound_ports, self.bidirectional_ports):
            if port.isBidirectional() == bidirectionality and (label is None or port.canMatchLabel(label)):
                if exclude and port.id_ == exclude:
                    continue
                matching_ports.append(port)
        return matching_ports


    def canSwapLabel(self, label_type):
        return False # not really clear how nml expresses this yet



class Topology(object):

    def __init__(self):
        self.networks = {} # network_name -> ( Network, nsa.NetworkServiceAgent)


    def addNetwork(self, network, managing_nsa):
        assert type(network) is Network
        assert type(managing_nsa) is nsa.NetworkServiceAgent

        if network.id_ in self.networks:
            raise error.TopologyError('Entry for network with id %s already exists' % network.id_)

        self.networks[network.id_] = (network, managing_nsa)


    def updateNetwork(self, network, managing_nsa):
        # update an existing network entry
        existing_entry = self.networks.pop(network.id_, None) # note - we may get none here (for new network)
        try:
            self.addNetwork(network, managing_nsa)
        except error.TopologyError as e:
            log.msg('Error updating network entry for %s. Reason: %s' % (network.id_, str(e)))
            if existing_entry:
                self.networks[network.id_] = existing_entry # restore old entry
            raise e


    def getNetwork(self, network_id):
        try:
            return self.networks[network_id][0]
        except KeyError:
            raise error.TopologyError('No network with id %s' % (network_id))


    def getNetworkPort(self, port_id):
        for network_id, (network,_) in self.networks.items():
            try:
                port = network.getPort(port_id)
                return network_id, port
            except error.TopologyError:
                continue
        else:
            raise error.TopologyError('Cannot find port with id %s in topology' % port_id)


    def getNSA(self, network_id):
        try:
            return self.networks[network_id][1]
        except KeyError as e:
            raise error.TopologyError('No NSA for network with id %s (%s)' % (network_id, str(e)))


    def findDemarcationPort(self, port):
        # finds - if it exists - the demarcation port of a bidirectional port - have to go through unidirectional model
        assert isinstance(port, BidirectionalPort), 'Specified port for demarcation find is not bidirectional'
        if not port.hasRemote():
            return None

        try:
            remote_network_in,  remote_port_in  = self.getNetworkPort(port.outbound_port.remote_port)
            remote_network_out, remote_port_out = self.getNetworkPort(port.inbound_port.remote_port)

            if remote_network_in != remote_network_out:
                log.msg('Bidirectional port %s leads to multiple networks. Topology screwup?' % port.id_, system=LOG_SYSTEM)
                return None

        except error.TopologyError as e:
            log.msg('Error looking up demarcation port for %s. Message: %s' % (port.id_, str(e)), system=LOG_SYSTEM)
            return None

        remote_network = self.getNetwork(remote_network_in)

        for rp in remote_network.findPorts(True):
            if isinstance(rp, BidirectionalPort) and rp.inbound_port.id_ == remote_port_in.id_ and rp.outbound_port.id_ == remote_port_out.id_:
                return remote_network.id_, rp.id_
        return None


    def findPaths(self, source_stp, dest_stp, bandwidth, exclude_networks=None):

        source_port = self.getNetwork(source_stp.network).getPort(source_stp.port)
        dest_port   = self.getNetwork(dest_stp.network).getPort(dest_stp.port)

        if source_port.isBidirectional() or dest_port.isBidirectional():
            # at least one of the stps are bidirectional
            if not source_port.isBidirectional():
                raise error.TopologyError('Cannot connect bidirectional source with unidirectional destination')
            if not dest_port.isBidirectional():
                raise error.TopologyError('Cannot connect bidirectional destination with unidirectional source')
        else:
            # both ports are unidirectional
            if not (source_port.orientation, dest_port.orientation) in ( (INGRESS, EGRESS), (EGRESS, INGRESS) ):
                raise error.TopologyError('Cannot connect STPs of same unidirectional direction (%s -> %s)' % (source_port.orientation, dest_port.orientation))

        # these are only really interesting for the initial call, afterwards they just prune
        if not source_port.canMatchLabel(source_stp.label):
            raise error.TopologyError('Source port %s (label %s) cannot match label for source STP (%s)' % (source_port.id_, source_port.label(), source_stp.label))
        if not dest_port.canMatchLabel(dest_stp.label):
            raise error.TopologyError('Desitination port %s (label %s) cannot match label for destination STP %s' % (dest_port.id_, dest_port.label(), dest_stp.label))
#        if not source_port.canProvideBandwidth(bandwidth):
#            raise error.BandwidthUnavailableError('Source port cannot provide enough bandwidth (%i)' % bandwidth)
#        if not dest_port.canProvideBandwidth(bandwidth):
#            raise error.BandwidthUnavailableError('Destination port cannot provide enough bandwidth (%i)' % bandwidth)

        return self._findPathsRecurse(source_stp, dest_stp, bandwidth)


    def _findPathsRecurse(self, source_stp, dest_stp, bandwidth, exclude_networks=None):

        source_network = self.getNetwork(source_stp.network)
        dest_network   = self.getNetwork(dest_stp.network)
        source_port    = source_network.getPort(source_stp.port)
        dest_port      = dest_network.getPort(dest_stp.port)

        if not (source_port.canMatchLabel(source_stp.label) or dest_port.canMatchLabel(dest_stp.label)):
            return []
#        if not (source_port.canProvideBandwidth(bandwidth) and dest_port.canProvideBandwidth(bandwidth)):
#            return []

        if source_port.isBidirectional() and dest_port.isBidirectional():
            # bidirectional path finding, easy case first
            if source_stp.network == dest_stp.network:
                # while it is possible to cross other network in order to connect to intra-network STPs
                # it is not something we really want to do in the real world, so we don't
                try:
                    if source_network.canSwapLabel(source_stp.label.type_):
                        source_label = source_port.label().intersect(source_stp.label)
                        dest_label   = dest_port.label().intersect(dest_stp.label)
                    else:
                        source_label = source_port.label().intersect(dest_port.label()).intersect(source_stp.label).intersect(dest_stp.label)
                        dest_label   = source_label
                    link = nsa.Link(source_stp.network, source_stp.port, dest_stp.port, source_label, dest_label)
                    return [ [ link ] ]
                except nsa.EmptyLabelSet:
                    return [] # no path
            else:
                # ok, time for real pathfinding
                link_ports = source_network.findPorts(True, source_stp.label, source_stp.port)
                link_ports = [ port for port in link_ports if port.hasRemote() ] # filter out termination ports
                links = []
                for lp in link_ports:
                    demarcation = self.findDemarcationPort(lp)
                    if demarcation is None:
                        continue

                    d_network_id, d_port_id = demarcation

                    if exclude_networks is not None and demarcation[0] in exclude_networks:
                        continue # don't do loops in path finding

                    demarcation_label = lp.label() if source_network.canSwapLabel(source_stp.label.type_) else source_stp.label.intersect(lp.label())
                    demarcation_stp = nsa.STP(demarcation[0], demarcation[1], demarcation_label)
                    sub_exclude_networks = [ source_network.id_ ] + (exclude_networks or [])
                    sub_links = self._findPathsRecurse(demarcation_stp, dest_stp, bandwidth, sub_exclude_networks)
                    # if we didn't find any sub paths, just continue
                    if not sub_links:
                        continue

                    for sl in sub_links:
                        # --
                        if source_network.canSwapLabel(source_stp.label.type_):
                            source_label = source_port.label().intersect(source_stp.label)
                            dest_label   = lp.label().intersect(sl[0].src_stp.label)
                        else:
                            source_label = source_port.label().intersect(source_stp.label).intersect(lp.label()).intersect(sl[0].src_stp.label)
                            dest_label   = source_label

                        first_link = nsa.Link(source_stp.network, source_stp.port, lp.id_, source_label, dest_label)
                        path = [ first_link ] + sl
                        links.append(path)

                return sorted(links, key=len) # sort by length, shortest first

        else:
            raise error.TopologyError('Unidirectional path-finding not implemented yet')



def createNMLNetwork(nrm_ports, network_name, network_readable_name):
    # create an nml network (topology) from a list of nrm ports

    inbound_ports       = []
    outbound_ports      = []
    bidirectional_ports = []

    for port in nrm_ports:

        assert port.port_type == cnt.NRM_ETHERNET, 'Sorry can only do ethernet ports for now'

        inbound_port_name   = port.name + '-in'
        outbound_port_name  = port.name + '-out'

        port_id             = network_name + ':' + port.name
        inbound_port_id     = network_name + ':' + inbound_port_name
        outbound_port_id    = network_name + ':' + outbound_port_name

        inbound_port        = InternalPort(inbound_port_id,  inbound_port_name,  port.bandwidth, port.label, port.remote_out)
        outbound_port       = InternalPort(outbound_port_id, outbound_port_name, port.bandwidth, port.label, port.remote_in)
        bidirectional_port  = BidirectionalPort(port_id, port.name, inbound_port, outbound_port, port.remote_port)

        inbound_ports.append(inbound_port)
        outbound_ports.append(outbound_port)
        bidirectional_ports.append(bidirectional_port)

    return Network(network_name, network_readable_name, inbound_ports, outbound_ports, bidirectional_ports)

