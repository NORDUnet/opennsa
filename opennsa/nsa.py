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


NSA = NetworkServiceAgent # short hand



class ServiceTerminationEndpoint:

    def __init__(self, network, endpoint):
        self.network = network
        self.endpoint = endpoint


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


