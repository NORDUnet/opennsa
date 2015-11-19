"""
NRM backends which just logs actions performed.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import string
import random

from twisted.python import log
from twisted.internet import defer

from opennsa.backends.common import genericbackend



def DUDNSIBackend(network_name, nrm_ports, parent_requester, configuration):

    name = 'DUD NRM %s' % network_name
    nrm_map  = dict( [ (p.name, p) for p in nrm_ports ] ) # for the generic backend
    port_map = dict( [ (p.name, p.interface) for p in nrm_ports ] ) # for the nrm backend

    cm = DUDConnectionManager(name, port_map)
    return genericbackend.GenericBackend(network_name, nrm_map, cm, parent_requester, name, minimum_duration=1)



class DUDConnectionManager:

    def __init__(self, log_system, port_map):
        self.log_system = log_system
        self.port_map   = port_map


    def getResource(self, port, label_type, label_value):
        return self.port_map[port] + ':' + str(label_value)


    def getTarget(self, port, label_type, label_value):
        return self.port_map[port] + '#' + str(label_value)


    def createConnectionId(self, source_target, dest_target):
        return 'DUD-' + ''.join( [ random.choice(string.hexdigits[:16]) for _ in range(8) ] )


    def canSwapLabel(self, label_type):
        return True
        #return False


    def setupLink(self, connection_id, source_target, dest_target, bandwidth):
        log.msg('Link %s -> %s up' % (source_target, dest_target), system=self.log_system)
        return defer.succeed(None)
        #from opennsa import error
        #return defer.fail(error.InternalNRMError('Link setup failed'))


    def teardownLink(self, connection_id, source_target, dest_target, bandwidth):
        log.msg('Link %s -> %s down' % (source_target, dest_target), system=self.log_system)
        return defer.succeed(None)
        #from opennsa import error
        #return defer.fail(error.InternalNRMError('Link teardown failed'))

