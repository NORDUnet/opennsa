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

from twisted.python import log
from twisted.internet import defer

from opennsa import nsa, error, state
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
        self.state = state.ConnectionState()


    def curator(self):
        return self._curator


    def stps(self):
        return nsa.STP(self.network_name, self.source_port), nsa.STP(self.network_name, self.dest_port)


    def logStateUpdate(self, state_msg):
        log.msg('Link: %s, %s -> %s : %s.' % (id(self), self.source_port, self.dest_port, state_msg), system=self.log_system)


    def reserve(self):

        def scheduled(st):
            self.state.switchState(state.SCHEDULED)
            self.scheduler.scheduleTransition(self.service_parameters.end_time, lambda _ : self.terminate(), state.TERMINATING)
            self.logStateUpdate('SCHEDULED')

        try:
            self.state.switchState(state.RESERVING)
            self.logStateUpdate('RESERVING')
            self.state.switchState(state.RESERVED)
        except error.StateTransitionError:
            return defer.fail(error.ReserveError('Cannot reserve connection in state %s' % self.state()))

        self.scheduler.scheduleTransition(self.service_parameters.start_time, scheduled, state.SCHEDULED)
        self.logStateUpdate('RESERVED')
        return defer.succeed(self)


    def provision(self):

        def provisionSuccess(_):
            self.scheduler.scheduleTransition(self.service_parameters.end_time, lambda _ : self.terminate(), state.TERMINATING)
            self.state.switchState(state.PROVISIONED)
            self.logStateUpdate('PROVISIONED')

        def provisionFailure(err):
            log.msg('Error setting up connection: %s' % err.getErrorMessage())
            self.state.switchState(state.TERMINATED)
            self.logStateUpdate('TERMINATED')
            return err

        def doProvision(_):
            try:
                self.state.switchState(state.PROVISIONING)
                self.logStateUpdate('PROVISIONING')
            except error.StateTransitionError:
                return defer.fail(error.ProvisionError('Cannot provision connection in state %s' % self.state()))

            d = self.connection_manager.setupLink(self.source_port, self.dest_port)
            d.addCallbacks(provisionSuccess, provisionFailure)
            return d


        dt_now = datetime.datetime.utcnow()
        if self.service_parameters.end_time <= dt_now:
            return defer.fail(error.ProvisionError('Cannot provision connection after end time (end time: %s, current time: %s).' % (self.service_parameters.end_time, dt_now)))

        self.state.switchState(state.AUTO_PROVISION) # This checks if we can switch into provision

        self.scheduler.cancelTransition() # cancel any pending scheduled switch

        if self.service_parameters.start_time <= dt_now:
            defer_provision = doProvision(None)
        else:
            defer_provision = self.scheduler.scheduleTransition(self.service_parameters.start_time, doProvision, state.PROVISIONING)
            self.logStateUpdate('PROVISION SCHEDULED')

        return defer.succeed(self), defer_provision



    def release(self):

        def releaseSuccess(_):
            self.scheduler.scheduleTransition(self.service_parameters.end_time, lambda _ : self.terminate(), state.TERMINATING)
            self.state.switchState(state.SCHEDULED)
            self.logStateUpdate('SCHEDULED')
            return self

        def releaseFailure(err):
            log.msg('Error releasing connection: %s' % err.getErrorMessage())
            self.state.switchState(state.TERMINATED)
            self.logStateUpdate('TERMINATED')
            return err

        try:
            self.state.switchState(state.RELEASING)
            self.logStateUpdate('RELEASING')
        except error.StateTransitionError:
            return defer.fail(error.ProvisionError('Cannot release connection in state %s' % self.state()))

        self.scheduler.cancelTransition() # cancel any pending scheduled switch

        d = self.connection_manager.teardownLink(self.source_port, self.dest_port)
        d.addCallbacks(releaseSuccess, releaseFailure)
        return d


    def terminate(self):

        def removeCalendarEntry():
            self.calendar.removeConnection(self.source_port, self.service_parameters.start_time, self.service_parameters.end_time)
            self.calendar.removeConnection(self.dest_port  , self.service_parameters.start_time, self.service_parameters.end_time)

        def terminateSuccess(_):
            removeCalendarEntry()
            self.state.switchState(state.TERMINATED)
            self.logStateUpdate(state.TERMINATED)
            return self

        def terminateFailure(err):
            log.msg('Error terminating connection: %s' % err.getErrorMessage())
            removeCalendarEntry() # This might be wrong :-/
            self.state.switchState(state.TERMINATED)
            self.logStateUpdate(state.TERMINATED)
            return err

        teardown = True if self.state() == state.PROVISIONED else False

        self.state.switchState(state.TERMINATING) # we can (almost) always switch to this
        self.logStateUpdate(state.TERMINATING)
        self.scheduler.cancelTransition() # cancel any pending scheduled switch

        if teardown:
            self.state.switchState(state.CLEANING)
            self.logStateUpdate(state.CLEANING)
            d = self.connection_manager.teardownLink(self.source_port, self.dest_port)
            d.addCallbacks(terminateSuccess, terminateFailure)
            return d
        else:
            return terminateSuccess(None)


    def query(self, query_filter):
        pass


