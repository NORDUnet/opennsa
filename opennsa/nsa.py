"""
Various "core" abstractions used in OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import urlparse


class ServiceTerminationEndpoint:

    def __init__(self, network, endpoint):
        self.network = network
        self.endpoint = endpoint

    def dict(self):
        return { 'network'  : self.network,
                 'endpoint' : self.endpoint }


STP = ServiceTerminationEndpoint # short hand



class NetworkServiceAgent:

    def __init__(self, address, service_attributes):
        self.address = address
        self.service_attributes = service_attributes


    def getHostPort(self):
        url = urlparse.urlparse(self.address)
        host, port = url.netloc.split(':',2)
        port = int(port)
        return host, port


    def dict(self):
        return { 'address' : self.address,
                 'service_attributes' : self.service_attributes }


NSA = NetworkServiceAgent # short hand



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

