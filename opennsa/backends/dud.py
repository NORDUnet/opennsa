"""
NRM backends which just logs actions performed.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from twisted.python import log
from twisted.internet import defer

from zope.interface import implements

from opennsa import interface as nsainterface
from opennsa.backends.common import calendar as reservationcalendar, simplebackend



class DUDNSIBackend:

    implements(nsainterface.NSIBackendInterface)

    def __init__(self, network_name):
        self.network_name = network_name
        self.calendar = reservationcalendar.ReservationCalendar()
        self.connections = []
        self.connection_manager = DUDConnectionManager('DUD Connection Manager %s' % network_name)


    def createConnection(self, source_port, dest_port, service_parameters):

        # probably need a short hand for this
        self.calendar.checkReservation(source_port, service_parameters.start_time, service_parameters.end_time)
        self.calendar.checkReservation(dest_port  , service_parameters.start_time, service_parameters.end_time)

        self.calendar.addConnection(source_port, service_parameters.start_time, service_parameters.end_time)
        self.calendar.addConnection(dest_port  , service_parameters.start_time, service_parameters.end_time)

        ac = simplebackend.GenericConnection(source_port, dest_port, service_parameters, self.network_name, self.calendar,
                                             'DUD NRM', 'DUD Network %s' % self.network_name, self.connection_manager)
        self.connections.append(ac)
        return ac



class DUDConnectionManager:

    def __init__(self, log_system):
        self.log_system = log_system


    def setupLink(self, source_port, dest_port):
        log.msg('Link %s -> %s up' % (source_port, dest_port), system=self.log_system)
        return defer.succeed(None)
        #return defer.fail(NotImplementedError('Link setup failed'))


    def teardownLink(self, source_port, dest_port):
        log.msg('Link %s -> %s down' % (source_port, dest_port), system=self.log_system)
        return defer.succeed(None)
        #return defer.fail(NotImplementedError('Link teardown failed'))

