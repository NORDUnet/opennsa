"""
Generic backend for deployments where OpenNSA is the only NRM (i.e. there is no
other system for interacting with the hardware).

Using this module, such a backend will only have to supply functionality for
setting up and tearing down links and does not have to deal state management.

The use this module a connection manager has to be supplied. The methods
setupLink(source_port, dest_port) and tearDown(source_port, dest_port) must be
implemented in the manager. The methods should return a deferred.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

import datetime

from dateutil.tz import tzutc

from twisted.python import log
from twisted.internet import defer

from opennsa import error, state
from opennsa.backends.common import scheduler



class GenericConnection:

    def __init__(self, source_port, dest_port, service_parameters, network_name, calendar, curator, log_system, connection_manager):
        self.source_port = source_port
        self.dest_port  = dest_port
        self.service_parameters = service_parameters
        self.network_name = network_name
        self.calendar = calendar

        self._curator = curator
        self.log_system = log_system
        self.connection_manager = connection_manager

        self.scheduler = scheduler.TransitionScheduler()
        self.state = state.NSI2StateMachine()


    def curator(self):
        return self._curator


    def stps(self):
        return self.service_parameters.source_stp, self.service_parameters.dest_stp


    def logStateUpdate(self, state_msg):
        log.msg('Link: %s, %s -> %s : %s.' % (id(self), self.source_port, self.dest_port, state_msg), system=self.log_system)


    def reserve(self):

        # return defer.fail( error.InternalNRMError('test reservation failure') )

        def scheduled():
            self.state.scheduled()
            self.scheduler.scheduleTransition(self.service_parameters.end_time, self.terminate, state.TERMINATING)
            self.logStateUpdate('SCHEDULED')

        self.state.reserving()
        self.logStateUpdate('RESERVING')
        self.state.reserved()
        self.logStateUpdate('RESERVED')
        self.scheduler.scheduleTransition(self.service_parameters.start_time, scheduled, state.SCHEDULED)
        return defer.succeed(self)


    def provision(self):

        def activationSuccess(_):
            self.scheduler.scheduleTransition(self.service_parameters.end_time, self.terminate, state.TERMINATING)
            self.state.active()
            self.logStateUpdate('ACTIVE')

        def activationFailure(err):
            log.msg('Error setting up connection: %s' % err.getErrorMessage())
            self.state.inactive()
            self.logStateUpdate('INACTIVE')
            return err

        def doActivate():
            self.state.activating()
            self.logStateUpdate('ACTIVATING')

            d = self.connection_manager.setupLink(self.source_port, self.dest_port)
            d.addCallbacks(activationSuccess, activationFailure)
            return d

        dt_now = datetime.datetime.now(tzutc())
        if self.service_parameters.end_time <= dt_now:
            return defer.fail(error.ConnectionGone('Cannot provision connection after end time (end time: %s, current time: %s).' % (self.service_parameters.end_time, dt_now)))

        self.state.provisioning()
        self.scheduler.cancelTransition() # cancel any pending scheduled switch

        if self.service_parameters.start_time <= dt_now:
            defer_provision = doActivate()
        else:
            defer_provision = self.scheduler.scheduleTransition(self.service_parameters.start_time, doActivate, state.ACTIVATING)

        self.state.provisioned()
        self.logStateUpdate('PROVISIONED')
        return defer.succeed(self)



    def release(self):

        def deactivateSuccess(_):
            self.scheduler.scheduleTransition(self.service_parameters.end_time, self.terminating, state.TERMINATING)
            self.state.inactive()
            self.logStateUpdate('INACTIVE')
            self.state.released()
            self.logStateUpdate('RELEASED')
            return self

        def deactivateFailure(err):
            log.msg('Error deactivating connection: %s' % err.getErrorMessage())
            self.state.terminatedFailure()
            self.logStateUpdate('TERMINATED FAILURE')
            return err

        self.state.releasing()
        self.logStateUpdate('RELEASING')
        self.scheduler.cancelTransition()

        # we need to handle activating somehow...
        if self.state.isActive():
            self.state.deactivating()
            self.logStateUpdate('DEACTIVATING')
            d = self.connection_manager.teardownLink(self.source_port, self.dest_port)
            d.addCallbacks(deactivateSuccess, deactivateFailure)
        else:
            self.state.released()
            d = defer.succeed(self)

        return d


    def terminate(self):

        # return defer.fail( error.InternalNRMError('test termination failure') )

        def removeCalendarEntry():
            self.calendar.removeConnection(self.source_port, self.service_parameters.start_time, self.service_parameters.end_time)
            self.calendar.removeConnection(self.dest_port  , self.service_parameters.start_time, self.service_parameters.end_time)

        def terminateSuccess(_):
            removeCalendarEntry()
            self.state.terminatedEndtime()
            self.logStateUpdate('TERMINATED ENDTIME')
            return defer.succeed(self)

        def terminateFailure(err):
            log.msg('Error terminating connection: %s' % err.getErrorMessage())
            removeCalendarEntry() # This might be wrong :-/
            self.state.terminatedFailure()
            self.logStateUpdate('TERMINATED FAILURE')
            return err

        if self.state.isTerminated():
            return defer.succeed(self)

        self.state.terminating()
        self.logStateUpdate(state.TERMINATING)
        self.scheduler.cancelTransition()

        if self.state.isActive():
            self.state.deactivating()
            self.logStateUpdate(state.DEACTIVATING)
            d = self.connection_manager.teardownLink(self.source_port, self.dest_port)
            d.addCallbacks(terminateSuccess, terminateFailure)
            return d
        else:
            return terminateSuccess(None)


    def query(self, query_filter):
        pass


