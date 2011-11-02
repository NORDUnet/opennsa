"""
NRM backends which just logs actions performed.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import datetime

from twisted.python import log
from twisted.internet import reactor, defer, task

from zope.interface import implements

from opennsa import nsa, error, state, interface as nsainterface
from opennsa.backends.common import calendar as reservationcalendar



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



def deferTaskFailed(err):
    if err.check(defer.CancelledError):
        pass # this just means that the task was cancelled
    else:
        log.err(err)



class DUDConnection:

    def __init__(self, source_port, dest_port, service_parameters, network_name, calendar):
        self.source_port = source_port
        self.dest_port  = dest_port
        self.service_parameters = service_parameters
        self.network_name = network_name
        self.calendar = calendar

        self.state = state.ConnectionState()
        self.auto_transition_deferred = None


    def stps(self):
        return nsa.STP(self.network_name, self.source_port), nsa.STP(self.network_name, self.dest_port)


    def deSchedule(self):

        if self.auto_transition_deferred:
            log.msg('Cancelling automatic state transition.  CID %s' % id(self), system='DUDBackend Network %s' % self.network_name)
            self.auto_transition_deferred.cancel()
            self.auto_transition_deferred = None


    def reserve(self):

        log.msg('RESERVE. CID: %s, Ports: %s -> %s' % (id(self), self.source_port, self.dest_port), system='DUDBackend Network %s' % self.network_name)
        try:
            self.state.switchState(state.RESERVING)
            self.state.switchState(state.RESERVED)
        except error.StateTransitionError:
            return defer.fail(error.ReserveError('Cannot reserve connection in state %s' % self.state()))
        # need to schedule transition to SCHEDULED
        return defer.succeed(self)


    def provision(self):

        def doProvision():
            log.msg('PROVISION. CID: %s' % id(self), system='DUDBackend Network %s' % self.network_name)
            self.deSchedule()
            try:
                self.state.switchState(state.PROVISIONING)
            except error.StateTransitionError:
                return defer.fail(error.ProvisionError('Cannot provision connection in state %s' % self.state()))
            # schedule release
            td = self.service_parameters.end_time -  datetime.datetime.utcnow()
            # total_seconds() is only available from python 2.7 so we use this
            stop_delta_seconds = (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6.0

            self.auto_transition_deferred = task.deferLater(reactor, stop_delta_seconds, self.release)
            self.auto_transition_deferred.addErrback(deferTaskFailed)
            self.state.switchState(state.PROVISIONED)

        dt_now = datetime.datetime.utcnow()

        if self.service_parameters.end_time <= dt_now:
            return defer.fail(error.ProvisionError('Cannot provision connection after end time (end time: %s, current time: %s).' % (self.service_parameters.end_time, dt_now)))
        else:
            td = self.service_parameters.start_time - dt_now
            # total_seconds() is only available from python 2.7 so we use this
            start_delta_seconds = (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6.0
            start_delta_seconds = max(start_delta_seconds, 0) # if we dt_now during calculation

            self.auto_transition_deferred = task.deferLater(reactor, start_delta_seconds, doProvision)
            self.auto_transition_deferred.addErrback(deferTaskFailed)
            self.state.switchState(state.AUTO_PROVISION)
            log.msg('Connection %s scheduled for auto-provision in %i seconds ' % (id(self), start_delta_seconds), system='DUDBackend Network %s' % self.network_name)

        return defer.succeed(self)


    def release(self):

        log.msg('RELEASE. CID: %s' % id(self), system='DUDBackend Network %s' % self.network_name)
        self.deSchedule()
        try:
            self.state.switchState(state.RELEASING)
        except error.StateTransitionError, e:
            log.msg('Release error: ' + str(e), system='DUDBackend Network %s' % self.network_name)
            return defer.fail(e)

        self.state.switchState(state.SCHEDULED)
        return defer.succeed(self)


    def terminate(self):

        log.msg('TERMINATE. CID : %s' % id(self), system='DUDBackend Network %s' % self.network_name)

        self.deSchedule()
        self.calendar.removeConnection(self.source_port, self.service_parameters.start_time, self.service_parameters.end_time)
        self.calendar.removeConnection(self.dest_port  , self.service_parameters.start_time, self.service_parameters.end_time)

        self.state.switchState(state.TERMINATED)
        return defer.succeed(self)


    def query(self, query_filter):
        pass


