"""
NRM backends which just logs actions performed.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import datetime

from twisted.python import log
from twisted.internet import defer

from zope.interface import implements

from opennsa import nsa, error, state, interface as nsainterface
from opennsa.backends.common import scheduler, calendar as reservationcalendar



class DUDNSIBackend:

    implements(nsainterface.NSIBackendInterface)

    def __init__(self, network_name):
        self.network_name = network_name
        self.calendar = reservationcalendar.ReservationCalendar()
        self.connections = []


    def createConnection(self, source_port, dest_port, service_parameters):

        # probably need a short hand for this
        self.calendar.checkReservation(source_port, service_parameters.start_time, service_parameters.end_time)
        self.calendar.checkReservation(dest_port  , service_parameters.start_time, service_parameters.end_time)

        self.calendar.addConnection(source_port, service_parameters.start_time, service_parameters.end_time)
        self.calendar.addConnection(dest_port  , service_parameters.start_time, service_parameters.end_time)

        ac = DUDConnection(source_port, dest_port, service_parameters, self.network_name, self.calendar)
        self.connections.append(ac)
        return ac



class DUDConnection:

    def __init__(self, source_port, dest_port, service_parameters, network_name, calendar):
        self.source_port = source_port
        self.dest_port  = dest_port
        self.service_parameters = service_parameters
        self.network_name = network_name
        self.calendar = calendar

        self.scheduler = scheduler.TransitionScheduler()
        self.state = state.ConnectionState()


    def curator(self):
        # the entity responsible for connection, mainly used for logging
        return 'DUD NRM'


    def stps(self):
        return nsa.STP(self.network_name, self.source_port), nsa.STP(self.network_name, self.dest_port)


    def reserve(self):

        def scheduled(st):
            self.state.switchState(state.SCHEDULED)
            self.scheduler.scheduleTransition(self.service_parameters.end_time, lambda _ : self.terminate(), state.TERMINATING)

        log.msg('RESERVING. CID: %s, Ports: %s -> %s' % (id(self), self.source_port, self.dest_port), system='DUDBackend Network %s' % self.network_name)
        try:
            self.state.switchState(state.RESERVING)
            self.state.switchState(state.RESERVED)
        except error.StateTransitionError:
            return defer.fail(error.ReserveError('Cannot reserve connection in state %s' % self.state()))

        self.scheduler.scheduleTransition(self.service_parameters.start_time, scheduled, state.SCHEDULED)
        return defer.succeed(self)


    def provision(self):

        def doProvision(_):
            log.msg('PROVISIONING. CID: %s' % id(self), system='DUDBackend Network %s' % self.network_name)
            try:
                self.state.switchState(state.PROVISIONING)
            except error.StateTransitionError:
                return defer.fail(error.ProvisionError('Cannot provision connection in state %s' % self.state()))

            self.scheduler.scheduleTransition(self.service_parameters.end_time, lambda _ : self.terminate(), state.TERMINATING)
            self.state.switchState(state.PROVISIONED)

        dt_now = datetime.datetime.utcnow()
        if self.service_parameters.end_time <= dt_now:
            return defer.fail(error.ProvisionError('Cannot provision connection after end time (end time: %s, current time: %s).' % (self.service_parameters.end_time, dt_now)))

        self.state.switchState(state.AUTO_PROVISION)
        self.scheduler.cancelTransition() # cancel any pending scheduled switch

        if self.service_parameters.start_time <= dt_now:
            doProvision(state.PROVISIONING)
        else:
            self.scheduler.scheduleTransition(self.service_parameters.start_time, doProvision, state.PROVISIONING)

        return defer.succeed(self)


    def release(self):

        log.msg('RELEASING. CID: %s' % id(self), system='DUDBackend Network %s' % self.network_name)
        try:
            self.state.switchState(state.RELEASING)
        except error.StateTransitionError, e:
            log.msg('Release error: ' + str(e), system='DUDBackend Network %s' % self.network_name)
            return defer.fail(e)

        self.scheduler.cancelTransition() # cancel any pending scheduled switch
        self.scheduler.scheduleTransition(self.service_parameters.end_time, lambda _ : self.terminate(), state.TERMINATING)
        self.state.switchState(state.SCHEDULED)
        return defer.succeed(self)


    def terminate(self):

        log.msg('TERMINATING. CID : %s' % id(self), system='DUDBackend Network %s' % self.network_name)

        self.state.switchState(state.TERMINATING)
        self.scheduler.cancelTransition() # cancel any pending scheduled switch

        self.calendar.removeConnection(self.source_port, self.service_parameters.start_time, self.service_parameters.end_time)
        self.calendar.removeConnection(self.dest_port  , self.service_parameters.start_time, self.service_parameters.end_time)

        self.state.switchState(state.TERMINATED)
        return defer.succeed(self)


    def query(self, query_filter):
        pass


