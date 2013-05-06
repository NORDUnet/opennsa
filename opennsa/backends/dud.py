"""
NRM backends which just logs actions performed.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from twisted.python import log
from twisted.internet import defer

from opennsa import registry
from opennsa.backends.common import simplebackend



class DUDNSIBackend(simplebackend.SimpleBackend):

    def __init__(self, network_name, service_registry):

        cm = connection_manager = DUDConnectionManager('DUD Connection Manager %s' % network_name)
        simplebackend.SimpleBackend.__init__(self, network_name, cm, 'DUD NRM')
        self.service_registry = service_registry

    def startService(self):

        simplebackend.SimpleBackend.startService(self)

        self.service_registry.registerEventHandler(registry.RESERVE,   self.reserve,   registry.NSI2_LOCAL)
        self.service_registry.registerEventHandler(registry.PROVISION, self.provision, registry.NSI2_LOCAL)
        self.service_registry.registerEventHandler(registry.RELEASE,   self.release,   registry.NSI2_LOCAL)
        self.service_registry.registerEventHandler(registry.TERMINATE, self.terminate, registry.NSI2_LOCAL)



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

