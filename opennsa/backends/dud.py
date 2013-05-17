"""
NRM backends which just logs actions performed.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from twisted.python import log
from twisted.internet import defer

from opennsa.backends.common import simplebackend



class DUDNSIBackend(simplebackend.SimpleBackend):

    def __init__(self, network_name, service_registry):

        name = 'DUD NRM %s' % network_name
        cm = DUDConnectionManager(name)
        simplebackend.SimpleBackend.__init__(self, network_name, cm, service_registry, name)



class DUDConnectionManager:

    def __init__(self, log_system):
        self.log_system = log_system


    def getResource(self, port, label_type, label_value):
        return port


    def getTarget(self, port, label_type, label_value):
        return port + '#' + label_value


    def canSwapLabel(self, label_type):
        #return True
        return False


    def setupLink(self, source_port, dest_port):
        log.msg('Link %s -> %s up' % (source_port, dest_port), system=self.log_system)
        return defer.succeed(None)
        #from opennsa import error
        #return defer.fail(error.InternalNRMError('Link setup failed'))


    def teardownLink(self, source_port, dest_port):
        log.msg('Link %s -> %s down' % (source_port, dest_port), system=self.log_system)
        return defer.succeed(None)
        #from opennsa import error
        #return defer.fail(error.InternalNRMError('Link teardown failed'))

