"""
Core abstractions used in OpenNSA.

In design pattern terms, these would be Data Transfer Objects (DTOs).
Though some of them do actually have some functionality methods.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2013)
"""


import urlparse

from opennsa import error



STP_PREFIX = 'urn:ogf:network:stp:'
NSA_PREFIX = 'urn:ogf:network:nsa:'

LOG_SYSTEM = 'opennsa.nsa'

# STP orientations
INGRESS = 'Ingress'
EGRESS  = 'Egress'
BIDIRECTIONAL = 'Bidirectional' # NSI1 compat



class Label:

    def __init__(self, type_, values=None):

        def createValue(value):
            if '-' in value:
                v1, v2 = value.split('-', 1)
                return int(v1), int(v2)
            try:
                v = int(value)
                return v, v
            except ValueError:
                raise error.TopologyError('Label %s is not an integer an integer range.' % value)

        assert type(values) in (None, str, list), 'Label values must be a list, was given %s' % values

        self.type_ = type_

        if values is not None:
            if type(values) is str:
                values = values.split(',')
            self.values = [ createValue(value) for value in values ]


    def __eq__(self, other):
        if not isinstance(other, Label):
            return False
        return self.type_ == other.type_ and sorted(self.values) == sorted(other.values)


    def __repr__(self):
        vs = [ str(v1) if v1 == v2 else str(v1) + '-' + str(v2) for v1,v2 in self.values ]
        return '<Label %s:%s>' % (self.type_, ','.join( vs ) )



class STP: # Service Termination Point

    def __init__(self, network, endpoint, orientation=BIDIRECTIONAL, labels=None):
        assert type(network) is str, 'Invalid network type provided for STP'
        assert type(endpoint) is str, 'Invalid endpoint type provided for STP'
        assert orientation in (INGRESS, EGRESS, BIDIRECTIONAL), 'Invalid orientation provided for STP'
        self.network = network
        self.endpoint = endpoint
        self.orientation = orientation
        self.labels = labels or []


    def urn(self):
        return STP_PREFIX + self.network + ':' + self.endpoint


    def __eq__(self, other):
        if not isinstance(other, STP):
            return False
        return self.network == other.network and self.endpoint == other.endpoint and self.labels == other.labels


    def __str__(self):
        return '<STP %s:%s>' % (self.network, self.endpoint)



class Link: # intra network link

    def __init__(self, network, src_port, dst_port, src_orientation, dst_orientation, src_labels=None, dst_labels=None):
        self.network = network
        self.src_port = src_port
        self.dst_port = dst_port
        self.src_orientation = src_orientation
        self.dst_orientation = dst_orientation
        self.src_labels = src_labels
        self.dst_labels = dst_labels


    def sourceSTP(self):
        return STP(self.network, self.src_port, self.src_orientation, self.src_labels)


    def destSTP(self):
        return STP(self.network, self.dst_port, self.dst_orientation, self.dst_labels)


    def __eq__(self, other):
        if not isinstance(other, Link):
            return False
        return (self.network, self.src_port, self.dst_port, self.src_orientation, self.dst_orientation, self.src_labels, self.dst_labels) == \
               (other.network, other.src_port, other.dst_port, other.src_orientation, other.dst_orientation, other.src_labels, other.dst_labels)


    def __str__(self):
        return '<Link %s::%s=%s>' % (self.network, self.source, self.dest)




class Path:
    """
    Represent a path from a source and destitionation STP, with the endpoint pairs between them.
    """
    def __init__(self, network_links):
        self.network_links = network_links


    def links(self):
        return self.network_links


    def sourceEndpoint(self):
        return self.network_links[0].sourceSTP()


    def destEndpoint(self):
        return self.network_links[-1].destSTP()


    def __str__(self):
        return '<Path: ' + ' '.join( [ str(nl) for nl in self.network_links ] ) + '>'



class NetworkEndpoint(STP):

    def __init__(self, network, endpoint, nrm_port=None, dest_stp=None, max_capacity=None, available_capacity=None):
        STP.__init__(self, network, endpoint)
        if nrm_port is not None:
            assert type(nrm_port) is str, 'Invalid nrm_port type provided for NetworkEndpoint initialization'
        self.nrm_port = nrm_port
        self.dest_stp = dest_stp
        self.max_capacity = max_capacity
        self.available_capacity = available_capacity


    def nrmPort(self):
        assert self.nrm_port is not None, 'No NRM port defined for NetworkEndpoint %s' % str(self)
        return self.nrm_port


    def __str__(self):
        return '<NetworkEndpoint %s:%s-%s#%s>' % (self.network, self.endpoint, self.dest_stp, self.nrm_port)



class NetworkServiceAgent:

    def __init__(self, identity, endpoint): #, service_attributes=None):
        assert type(identity) is str, 'NSA identity type must be string (type: %s, value %s)' % (type(identity), identity)
        assert type(endpoint) is str, 'NSA endpoint type must be string (type: %s, value %s)' % (type(endpoint), endpoint)
        self.identity = identity
        self.endpoint = endpoint.strip()


    def getHostPort(self):
        url = urlparse.urlparse(self.endpoint)
        host, port = url.netloc.split(':',2)
        port = int(port)
        return host, port


    def url(self):
        return self.endpoint


    def urn(self):
        return NSA_PREFIX + self.identity


    def __str__(self):
        return '<NetworkServiceAgent %s>' % self.identity



class Network:

    def __init__(self, name, nsa):
        self.name = name
        self.nsa = nsa
        self.endpoints = []


    def addEndpoint(self, endpoint):
        self.endpoints.append(endpoint)


    def getEndpoint(self, endpoint_name):
        for ep in self.endpoints:
            if ep.endpoint == endpoint_name:
                return ep

        raise error.TopologyError('No such endpoint (%s)' % (endpoint_name))


    def __str__(self):
        return '<Network %s,%i>' % (self.name, len(self.endpoints))



class ServiceParameters:

    def __init__(self, start_time, end_time, source_stp, dest_stp, bandwidth, stps=None, directionality='Bidirectional'):

        # should probably make path object sometime..

        # schedule
        self.start_time = start_time
        self.end_time   = end_time
        # path
        self.source_stp = source_stp
        self.dest_stp   = dest_stp
        self.bandwidth  = bandwidth

        self.stps       = stps
        assert directionality in ('Unidirectional', 'Bidirectional'), 'Invalid directionality: %s' % directionality
        self.directionality = directionality


    def subConnectionClone(self, source_stp, dest_stp):
        return ServiceParameters(self.start_time, self.end_time, source_stp, dest_stp, self.bandwidth, None, self.directionality)


    def protoSP(self):
        return { 'start_time' : self.start_time,
                 'end_time'   : self.end_time,
                 'source_stp' : self.source_stp.urn(),
                 'dest_stp'   : self.dest_stp.urn(),
                 'stps'       : self.stps        }


    def __str__(self):
        return '<ServiceParameters %s>' % str(self.protoSP())

