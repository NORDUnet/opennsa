"""
Core abstractions used in OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""


import urlparse



class STP: # Service Termination Point

    def __init__(self, network, endpoint):
        self.network = network
        self.endpoint = endpoint


    def protoSTP(self):
        return { 'network'  : self.network,
                 'endpoint' : self.endpoint }


    def __eq__(self, other):
        if not isinstance(other, STP):
            return False
        return self.network == other.network and self.endpoint == other.endpoint


    def __str__(self):
        return '<STP %s:%s>' % (self.network, self.endpoint)



class STPPair:

    def __init__(self, stp1, stp2):
        self.stp1 = stp1
        self.stp2 = stp2


    def __eq__(self, other):
        if not isinstance(other, STPPair):
            return False
        return self.stp1 == other.stp1 and self.stp2 == other.stp2


    def __str__(self):
        return '<STPPair %s:%s-%s:%s>' % (self.stp1.network, self.stp1.endpoint, self.stp2.network, self.stp2.endpoint)



class NetworkEndpoint(STP):

    def __init__(self, network, endpoint, config, dest_stp=None):
        STP.__init__(self, network, endpoint)
        self.config = config
        self.dest_stp = dest_stp


    def __str__(self):
        return '<NetworkEndpoint %s:%s-%s#%s>' % (self.network, self.endpoint, self.dest_stp, self.config)



class NetworkServiceAgent:

    def __init__(self, address, service_attributes=None, protocol=None):
        self.address = address
        self.service_attributes = service_attributes
        self.protocol = protocol or 'nsa-jsonrpc'


    def getHostPort(self):
        url = urlparse.urlparse(self.address)
        host, port = url.netloc.split(':',2)
        port = int(port)
        return host, port


    def protoNSA(self):
        return { 'address' : self.address,
                 'service_attributes' : self.service_attributes }


    def __str__(self):
        return '<NetworkServiceAgent %s,%s>' % (self.address, self.protocol)



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

    def __init__(self, start_time, end_time, source_stp, dest_stp, stps=None):
        # scheudle
        self.start_time = start_time
        self.end_time   = end_time
        # path
        self.source_stp = source_stp
        self.dest_stp   = dest_stp
        self.stps       = stps


    def protoSP(self):
        return { 'start_time' : self.start_time,
                 'end_time'   : self.end_time,
                 'source_stp' : self.source_stp.protoSTP(),
                 'dest_stp'   : self.dest_stp.protoSTP(),
                 'stps'       : self.stps        }


    def __str__(self):
        return '<ServiceParameters %s>' % str(self.protoSP())



RESERVING = 'RESERVING'
RESERVED  = 'RESERVED'



class SubConnection:

    def __init__(self, source_stp, dest_stp, network, connection_id):
        self.source_stp = source_stp
        self.dest_stp   = dest_stp
        self.network    = network
        self.connection_id = connection_id

        self.state = RESERVING



class Connection:

    def __init__(self, connection_id, internal_reservation_id, source_stp, dest_stp, global_reservation_id=None, sub_connections=None, internal_connection_id=None):
        self.connection_id              = connection_id
        self.internal_reservation_id    = internal_reservation_id
        self.internal_connection_id     = internal_connection_id # pretty much never available at creation
        self.source_stp                 = source_stp
        self.dest_stp                   = dest_stp
        self.global_reservation_id      = global_reservation_id
        self.sub_connections            = sub_connections or []

        self.state = RESERVING


    def setState(self, new_state):
        raise NotImplementedError('State changing not yet implemented')

