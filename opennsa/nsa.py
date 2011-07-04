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
        return '<ServiceTerminationEndpoint %s:%s>' % (self.network, self.endpoint)



class STPPair:

    def __init__(self, stp1, stp2):
        self.stp1 = stp1
        self.stp2 = stp2


    def __eq__(self, other):
        if not isinstance(other, STPPair):
            return False
        return self.stp1 == other.stp1 and self.stp2 == other.stp2



class NetworkEndpoint(STP):

    def __init__(self, network, endpoint, config, dest_stp=None):
        STP.__init__(self, network, endpoint)
        self.config = config
        self.dest_stp = dest_stp


    def __str__(self):
        return '<NetworkEndpoint %s:%s-%s#%s>' % (self.network, self.endpoint, self.dest_stp, self.config)



class Network:

    def __init__(self, name, nsa_address, nsa_service_attributes=None, protocol=None):
        self.name = name
        self.nsa_address = nsa_address
        self.nsa_service_attributes = nsa_service_attributes
        self.protocol = protocol or 'nsa-jsonrpc'
        self.endpoints = []


    def addEndpoint(self, endpoint):
        self.endpoints.append(endpoint)


    def getEndpoint(self, endpoint_name):
        for ep in self.endpoints:
            if ep.endpoint == endpoint_name:
                return ep

        raise TopologyError('No such endpoint (%s)' % (endpoint_name))


    def geNSAHostPort(self):
        url = urlparse.urlparse(self.address)
        host, port = url.netloc.split(':',2)
        port = int(port)
        return host, port


    def dict(self):
        return { 'address' : self.nsa_address,
                 'service_attributes' : self.nsa_service_attributes }


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


    def dict(self):
        return { 'start_time' : self.start_time,
                 'end_time'   : self.end_time,
                 'source_stp' : self.source_stp.dict(),
                 'dest_stp'   : self.dest_stp.dict(),
                 'stps'       : self.stps        }


    def __str__(self):
        return '<ServiceParameters %s>' % str(self.dict())



RESERVING = 'RESERVING'
RESERVED  = 'RESERVED'


class Connection:

    def __init__(self, connection_id, internal_reservation_id, source_stp, dest_stp, global_reservation_id=None, sub_reservations=None, internal_connection_id=None):
        self.connection_id              = connection_id
        self.internal_reservation_id    = internal_reservation_id
        self.internal_connection_id     = internal_connection_id # pretty much never available at creation
        self.source_stp                 = source_stp
        self.dest_stp                   = dest_stp
        self.global_reservation_id      = global_reservation_id
        self.sub_reservations           = sub_reservations

        self.state = RESERVING


    def state(self):
        return self.state


    def setState(self, new_state):
        raise NotImplementedError('State changing not yet implemented')

