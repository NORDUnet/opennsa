"""
NRM backends which just logs actions performed.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from twisted.python import log
from twisted.internet import defer

from zope.interface import implements

from opennsa import interface as nsainterface, registry
#from opennsa.backends.common import calendar as reservationcalendar, simplebackend
from opennsa.backends.common import simplebackend



class DUDNSIBackend:

    implements(nsainterface.NSIBackendInterface)

    def __init__(self, network_name, service_registry):
#        self.network_name = network_name
#        self.calendar = reservationcalendar.ReservationCalendar()
#        self.connections = []
#        self.connection_manager = DUDConnectionManager('DUD Connection Manager %s' % network_name)

        cm = connection_manager = DUDConnectionManager('DUD Connection Manager %s' % network_name)

        sc = simplebackend.SimpleBackend(network_name, cm, 'DUD NRM')

        service_registry.registerEventHandler(registry.RESERVE,   sc.reserve,   registry.NSI2_LOCAL)
        service_registry.registerEventHandler(registry.PROVISION, sc.provision, registry.NSI2_LOCAL)
        service_registry.registerEventHandler(registry.RELEASE,   sc.release,   registry.NSI2_LOCAL)
        service_registry.registerEventHandler(registry.TERMINATE, sc.terminate, registry.NSI2_LOCAL)


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

