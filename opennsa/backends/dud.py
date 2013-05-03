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


#    def canAllocateLink(self, source_port, dest_port, service_parameters):
#
#        self.calendar.checkReservation(source_port, service_parameters.start_time, service_parameters.end_time)
#        self.calendar.checkReservation(dest_port  , service_parameters.start_time, service_parameters.end_time)
#        return True
#
#
#    def createConnection(self, source_port, dest_port, service_parameters):
#
#        self.canAllocateLink(source_port, dest_port, service_parameters)
#
#        self.calendar.addConnection(source_port, service_parameters.start_time, service_parameters.end_time)
#        self.calendar.addConnection(dest_port  , service_parameters.start_time, service_parameters.end_time)
#
#        ac = simplebackend.GenericConnection(source_port, dest_port, service_parameters, self.network_name, self.calendar,
#                                             'DUD NRM', 'DUD Network %s' % self.network_name, self.connection_manager)
#        self.connections.append(ac)
#        return ac



class DUDConnectionManager:

    def __init__(self, log_system):
        self.log_system = log_system


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

