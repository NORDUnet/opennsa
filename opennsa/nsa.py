"""
Core abstractions used in OpenNSA.

In design pattern terms, these would be Data Transfer Objects (DTOs).
Though some of them do actually have some functionality methods.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2013)
"""


import uuid
import random
from urllib.parse import urlparse
import itertools

from opennsa import error, constants as cnt



LOG_SYSTEM = 'opennsa.nsa'

URN_UUID_PREFIX = 'urn:uuid:'

BIDIRECTIONAL   = 'Bidirectional'



class NSIHeader(object):

    def __init__(self, requester_nsa, provider_nsa, correlation_id=None, reply_to=None, security_attributes=None, connection_trace=None):
        self.requester_nsa          = requester_nsa
        self.provider_nsa           = provider_nsa
        self.correlation_id         = correlation_id or self._createCorrelationId()
        self.reply_to               = reply_to
        self.security_attributes    = security_attributes or []
        self.connection_trace       = connection_trace

    def _createCorrelationId(self):
        return URN_UUID_PREFIX + str(uuid.uuid1())

    def newCorrelationId(self):
        self.correlation_id = self._createCorrelationId()


    def __repr__(self):
        return '<NSIHeader: %s, %s, %s, %s, %s, %s>' % (self.requester_nsa, self.provider_nsa, self.correlation_id, self.reply_to, self.security_attributes, self.connection_trace)



class SecurityAttribute(object):
    # a better name would be AuthZAttribute, but we are keeping the NSI lingo

    def __init__(self, type_, value):
        assert type(type_) is str, 'SecurityAttribute type must be a string, not %s' % type(type_)
        assert type(value) is str, 'SecurityAttribute value must be a string, not %s' % type(value)
        self.type_ = type_
        self.value = value


    def __repr__(self):
        return '<SecurityAttribute: %s = %s>' % (self.type_, self.value)



class EmptyLabelSet(Exception):
    pass



class Label(object):

    def __init__(self, type_, values=None):

        assert type(values) in (None, str, list, int), 'Type of Label values must be a None, str, or list. Was given %s' % type(values)

        self.type_ = type_
        if type(values) is int:
            self.values = [ [values, values] ]
        else:
            self.values = self._parseLabelValues(values) if values is not None else None


    def _parseLabelValues(self, values):

        def createValue(value):
            try:
                if '-' in value:
                    v1, v2 = value.split('-', 1)
                    i1, i2 = int(v1), int(v2)
                    if i1 > i2:
                        raise error.PayloadError('Label value %s is in descending order, which is not allowed.' % value)
                else:
                    i1 = int(value)
                    i2 = i1
                return i1, i2
            except ValueError:
                raise error.PayloadError('Label %s is not an integer or an integer range.' % value)

        if type(values) is str:
            values = values.split(',')

        parsed_values = sorted( [ createValue(value) for value in values ] )

        # detect any overlap and remove it - remember that the list is sorted

        nv = [] # normalized values
        for v1, v2 in parsed_values:
            if len(nv) == 0:
                nv.append( (v1,v2) )
                continue

            l = nv[-1] # last
            if v1 <= l[1] + 1: # merge
                nv = nv[:-1] + [ (l[0], max(l[1],v2)) ]
            else:
                nv.append( (v1,v2) )

        return nv


    def intersect(self, other):
        # get the common values between two labels
        assert type(other) is Label, 'Cannot intersect label with something that is not a label (other was %s)' % type(other)
        assert self.type_ == other.type_, 'Cannot insersect label of different types'

        label_values = []
        i = iter(other.values)
        o1, o2 = next(i)

        for v1, v2 in self.values:
            while True:
                if v2 < o1:
                    break
                elif o2 < v1:
                    try:
                        o1, o2 = next(i)
                    except StopIteration:
                        break
                    continue
                label_values.append( ( max(v1,o1), min(v2,o2)) )
                if v2 <= o2:
                    break
                elif o2 <= v2:
                    try:
                        o1, o2 = next(i)
                    except StopIteration:
                        break

        if len(label_values) == 0:
            raise EmptyLabelSet('Label intersection produced empty label set')

        ls = ','.join( [ '%i-%s' % (nv[0], nv[1]) for nv in label_values ] )
        return Label(self.type_, ls)


    def labelValue(self):
        vs = [ str(v1) if v1 == v2 else str(v1) + '-' + str(v2) for v1,v2 in self.values ]
        return ','.join(vs)

    def singleValue(self):
        return len(self.values) == 1 and self.values[0][0] == self.values[0][1]

    def enumerateValues(self):
        lv = [ range(lr[0], lr[1]+1) for lr in self.values ]
        return list(itertools.chain.from_iterable( lv ) )

    def randomLabel(self):
        # not evenly distributed, but that isn't promised anyway
        label_range = random.choice(self.values)
        return random.randint(label_range[0], label_range[1]+1)

    @staticmethod
    def canMatch(l1, l2):
        if l1 is None and l2 is None:
            return True
        elif l1 is None or l2 is None:
            return False
        try:
            l1.intersect(l2) # this checks type as well as range
            return True
        except EmptyLabelSet:
            return False


    def __eq__(self, other):
        if not type(other) is Label:
            return False
        return self.type_ == other.type_ and sorted(self.values) == sorted(other.values)


    def __repr__(self):
        return '<Label %s:%s>' % (self.type_, self.labelValue())



class STP(object): # Service Termination Point

    def __init__(self, network, port, label=None):
        assert type(network) is str, 'Invalid network type provided for STP (got %s)' % type(network)
        assert type(port) is str, 'Invalid port type provided for STP (got %s)' % type(port)
        assert label is None or type(label) is Label, 'Invalid label type provided for STP'
        self.network = network
        self.port = port
        self.label = label


    def shortName(self):
        base = '%s:%s' % (self.network, self.port)
        if self.label:
            base += '?' + self.label.type_.split('#')[-1] + '=' + self.label.labelValue()
        return base


    def baseURN(self):
        return cnt.URN_OGF_PREFIX + self.network + ':' + self.port


    def urn(self):
        # one could probably do something clever with this and the above two functions
        label = ''
        if self.label is not None:
            label = '?' + self.label.type_.split('#')[-1] + '=' + self.label.labelValue()
        return self.baseURN() + label


    def __eq__(self, other):
        if not type(other) is STP:
            return False
        return self.network == other.network and self.port == other.port and self.label == other.label


    def __repr__(self):
        return '<STP %s>' % self.shortName()



class Link(object):

    def __init__(self, src_stp, dst_stp):
        self.src_stp = src_stp
        self.dst_stp = dst_stp


    def sourceSTP(self):
        return self.src_stp


    def destSTP(self):
        return self.dst_stp


    def __eq__(self, other):
        if not type(other) is Link:
            return False
        return (self.src_stp, self.dst_stp) == (other.src_stp, other.dst_stp)


    def __repr__(self):
        return '<Link %s == %s>' % (self.src_stp, self.dst_stp)



class Path(object):
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



class NetworkServiceAgent(object):

    def __init__(self, identity, endpoint, service_type=None):
        assert type(identity) is str, 'NSA identity type must be string (type: %s, value %s)' % (type(identity), identity)
        assert type(endpoint) is bytes, 'NSA endpoint type must be bytes (type: %s, value %s)' % (type(endpoint), endpoint)
        self.identity = identity
        self.endpoint = endpoint.strip() #.encode('utf-8')
        self.service_type = service_type


    def getHostPort(self):
        url = urlparse.urlparse(self.endpoint)
        host, port = url.netloc.split(':',2)
        port = int(port)
        return host, port


    def urn(self):
        return cnt.URN_OGF_PREFIX + self.identity


    def getServiceType(self):
        if self.service_type is None:
            raise ValueError('NSA with identity %s is not constructed with a type' % self.identity)
        return self.service_type


    def __str__(self):
        return '<NetworkServiceAgent %s>' % self.identity


class ConnectionInfo(object):
    # only used for query results

    def __init__(self, connection_id, global_reservation_id, description, service_type, criterias, provider_nsa, requester_nsa, states, notification_id, result_id):
        assert type(criterias) is list, 'Invalid criterias type: %s' % str(type(criterias))
        for criteria in criterias:
            assert type(criteria) is QueryCriteria, 'Invalid criteria type: %s' % str(type(criteria))
        self.connection_id          = connection_id
        self.global_reservation_id  = global_reservation_id
        self.description            = description
        self.service_type           = service_type
        self.criterias              = criterias
        self.provider_nsa           = provider_nsa
        self.requester_nsa          = requester_nsa
        self.states                 = states
        self.notification_id        = notification_id
        self.result_id              = result_id


class Criteria(object):

    def __init__(self, revision, schedule, service_def):
        self.revision    = revision
        self.schedule    = schedule
        self.service_def = service_def


class QueryCriteria(Criteria):
    # only used for query summary and recursive (but not really used in summary)

    def __init__(self, revision, schedule, service_def, children=None):
        assert children is None or type(children) is list, 'Invalid QueryCriteria type: %s' % str(type(children))
        for child in children or []:
            assert type(child) is ConnectionInfo, 'Invalid QueryCriteria child: %s' % str(type(child))
        Criteria.__init__(self, revision, schedule, service_def)
        self.children = children or []



class Schedule(object):

    def __init__(self, start_time, end_time):
        # Must be datetime instances without tzinfo
        if start_time is not None:
            assert start_time.tzinfo is None, 'Start time must NOT have time zone'
        if end_time is not None:
            assert end_time.tzinfo   is None, 'End time must NOT have time zone'

        self.start_time = start_time
        self.end_time   = end_time


    def __str__(self):
        return '<Schedule: %s-%s>' % (self.start_time, self.end_time)



class Point2PointService(object):

    def __init__(self, source_stp, dest_stp, capacity, directionality=BIDIRECTIONAL, symmetric=None, ero=None, parameters=None):

        if directionality is None:
            raise error.MissingParameterError('directionality must be defined, must not be None')

        self.source_stp     = source_stp
        self.dest_stp       = dest_stp
        self.capacity       = capacity
        self.directionality = directionality
        self.symmetric      = symmetric
        self.ero            = ero
        self.parameters     = parameters

