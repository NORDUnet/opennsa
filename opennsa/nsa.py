"""
Various "core" abstractions used in OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import urlparse


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



class ServiceTerminationEndpoint:

    def __init__(self, network, endpoint):
        self.network = network
        self.endpoint = endpoint

    def dict(self):
        return { 'network'  : self.network,
                 'endpoint' : self.endpoint }


STP = ServiceTerminationEndpoint # short hand



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


