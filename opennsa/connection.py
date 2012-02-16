"""
Connection abstraction.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

import datetime

from twisted.python import log, failure
from twisted.internet import defer

from opennsa import error, nsa, state, registry, subscription
from opennsa.backends.common import scheduler



LOG_SYSTEM = 'opennsa.Connection'



def connPath(conn):
    """
    Utility function for getting a string with the source and dest STP of connection.
    """
    source_stp, dest_stp = conn.stps()
    return '<%s:%s--%s:%s>' % (source_stp.network, source_stp.endpoint, dest_stp.network, dest_stp.endpoint)



class SubConnection:

    def __init__(self, client, requester_nsa, provider_nsa, parent_connection, connection_id, source_stp, dest_stp, service_parameters):
        self.client             = client
        self.requester_nsa      = requester_nsa # this the identity of the current nsa
        self.provider_nsa       = provider_nsa

        self.parent_connection  = parent_connection
        self.connection_id      = connection_id
        self.source_stp         = source_stp
        self.dest_stp           = dest_stp
        self.service_parameters = service_parameters

        self.session_security_attr = None


    def curator(self):
        return self.provider_nsa.identity


    def stps(self):
        return self.source_stp, self.dest_stp


    def reserve(self):

        def reserveDone(int_res_id):
            log.msg('Remote connection %s via %s reserved' % (connPath(self), self.provider_nsa), debug=True, system=LOG_SYSTEM)
            return self

        sub_service_params  = nsa.ServiceParameters(self.service_parameters.start_time,
                                                    self.service_parameters.end_time,
                                                    self.source_stp,
                                                    self.dest_stp,
                                                    directionality=self.service_parameters.directionality,
                                                    bandwidth=self.service_parameters.bandwidth)

        d = self.client.reserve(self.requester_nsa, self.provider_nsa, self.session_security_attr,
                                self.parent_connection.global_reservation_id, self.parent_connection.description, self.connection_id, sub_service_params)
        d.addCallback(reserveDone)
        return d


    def terminate(self):

        def terminateDone(int_res_id):
            log.msg('Remote connection %s via %s terminated' % (connPath(self), self.provider_nsa), debug=True, system=LOG_SYSTEM)
            return self

        d = self.client.terminate(self.requester_nsa, self.provider_nsa, self.session_security_attr, self.connection_id)
        d.addCallback(terminateDone)
        return d


    def provision(self):

        def provisionDone(int_res_id):
            log.msg('Remote connection %s via %s provisioned' % (connPath(self), self.provider_nsa), debug=True, system=LOG_SYSTEM)
            return self

        d = self.client.provision(self.requester_nsa, self.provider_nsa, self.session_security_attr, self.connection_id)
        d.addCallback(provisionDone)
        return defer.succeed(None), d


    def release(self):

        def releaseDone(int_res_id):
            log.msg('Remote connection %s via %s released' % (connPath(self), self.provider_nsa), debug=True, system=LOG_SYSTEM)
            return self

        d = self.client.release(self.requester_nsa, self.provider_nsa, self.session_security_attr, self.connection_id)
        d.addCallback(releaseDone)
        return d



class Connection:

    def __init__(self, service_registry, requester_nsa, connection_id, source_stp, dest_stp, service_parameters=None, global_reservation_id=None, description=None):
        self.state = state.ConnectionState()
        self.requester_nsa              = requester_nsa
        self.connection_id              = connection_id
        self.source_stp                 = source_stp
        self.dest_stp                   = dest_stp
        self.service_parameters         = service_parameters
        self.global_reservation_id      = global_reservation_id
        self.description                = description
        self.scheduler                  = scheduler.TransitionScheduler()
        self.sub_connections            = []

        self.subscriptions              = []
        self.service_registry           = service_registry


    def connections(self):
        return self.sub_connections


    def addSubscription(self, sub):
        self.subscriptions.append(sub)


    def eventDispatch(self, event, success, result):
        defs = []
        for sub in reversed(self.subscriptions):
            if sub.match(event):
                d = subscription.dispatchNotification(success, result, sub, self.service_registry)
                defs.append(d)
                self.subscriptions.remove(sub)

        if defs:
            return defer.DeferredList(defs)
        else:
            log.msg('No subscriptions for event %s (possible bug / warning)' % event, system=LOG_SYSTEM)
            return defer.succeed(None)


    def _buildErrorMessage(self, results, action):

        # should probably seperate loggin somehow
        failures = [ (conn, f) for (success, f), conn in zip(results, self.connections()) if success is False ]
        failure_msgs = [ conn.curator() + ' ' + connPath(conn) + ' ' + f.getErrorMessage() for (conn, f) in failures ]
        log.msg('Connection %s: %i/%i %s failed.' % (self.connection_id, len(failures), len(results), action), system=LOG_SYSTEM)
        for msg in failure_msgs:
            log.msg('* Failure: ' + msg, system=LOG_SYSTEM)

        # build the error message to send back
        if len(results) == 1:
            # only one connection, we just return the plain failure
            error_msg = failures[0][1].getErrorMessage()
        else:
            # multiple failures, here we build a more complicated error string
            error_msg = '%i/%i %s failed: %s' % (len(failures), len(results), action, '. '.join(failure_msgs))

        return error_msg


    def reserve(self):

        def scheduled(st):
            self.state.switchState(state.SCHEDULED)
            self.scheduler.scheduleTransition(self.service_parameters.end_time, self.state.switchState, state.TERMINATED)
            return self


        def reserveRequestsDone(results):
            successes = [ r[0] for r in results ]
            if all(successes):
                self.state.switchState(state.RESERVED)
                log.msg('Connection %s: Reserve succeeded' % self.connection_id, system=LOG_SYSTEM)
                self.scheduler.scheduleTransition(self.service_parameters.start_time, scheduled, state.SCHEDULED)
                self.eventDispatch(registry.RESERVE_RESPONSE, True, self)

            else:
                error_msg = self._buildErrorMessage(results, 'reservations')

                # terminate non-failed connections
                # currently we don't try and be too clever about cleaning, just do it, and switch state
                defs = []
                reserved_connections = [ conn for success,conn in results if success ]
                for rc in reserved_connections:
                    d = rc.terminate()
                    d.addCallbacks(
                        lambda c : log.msg('Succesfully terminated sub connection after partial reservation failure %s %s' % (c.curator(), connPath(c)) , system=LOG_SYSTEM),
                        lambda f : log.msg('Error terminating connection after partial-reservation failure: %s' % str(f), system=LOG_SYSTEM)
                    )
                    defs.append(d)
                dl = defer.DeferredList(defs)
                dl.addCallback(lambda _ : self.state.switchState(state.TERMINATED) )

                err = failure.Failure(error.ReserveError(error_msg))
                self.eventDispatch(registry.RESERVE_RESPONSE, False, err)


        self.state.switchState(state.RESERVING)

        defs = [ sc.reserve() for sc in self.connections() ]

        dl = defer.DeferredList(defs, consumeErrors=True)
        dl.addCallback(reserveRequestsDone) # never errbacks
        return dl


    def provision(self):

        def provisionComplete(results):
            successes = [ r[0] for r in results ]
            if all(successes):
                if self.state() == state.AUTO_PROVISION:
                    # cannot switch directly from auto-provision to provisioned,
                    self.state.switchState(state.PROVISIONING)

                self.state.switchState(state.PROVISIONED)
                self.scheduler.scheduleTransition(self.service_parameters.end_time, lambda _ : self.terminate(), state.TERMINATING)

                self.eventDispatch(registry.PROVISION_RESPONSE, True, self)

            else:
                # at least one provision failed, provisioned connections should be released
                error_msg = self._buildErrorMessage(results, 'provisions')

                if self.state() == state.AUTO_PROVISION:
                    self.state.switchState(state.PROVISIONING) # state machine isn't quite clear on what we should be here

                # release provisioned connections
                defs = []
                provisioned_connections = [ conn for success,conn in results if success ]
                for pc in provisioned_connections:
                    d = pc.release()
                    d.addCallbacks(
                        lambda c : log.msg('Succesfully released sub-connection after partial provision failure %s %s' % (c.curator(), connPath(c)), system=LOG_SYSTEM),
                        lambda f : log.msg('Error releasing connection after partial provision failure: %s' % str(f), system=LOG_SYSTEM)
                    )
                    defs.append(d)
                dl = defer.DeferredList(defs)
                dl.addCallback(lambda _ : self.state.switchState(state.SCHEDULED) )

                def releaseDone(_):
                    err = failure.Failure(error.ProvisionError(error_msg))
                    self.eventDispatch(registry.PROVISION_RESPONSE, False, err)

                dl.addCallback(releaseDone)

        # --

        # initial state switch (this validates if the transition is possible)
        if self.service_parameters.start_time > datetime.datetime.utcnow():
            self.state.switchState(state.AUTO_PROVISION)
        else:
            self.state.switchState(state.PROVISIONING)

        self.scheduler.cancelTransition() # cancel any pending scheduled switch

        defs = [ sc.provision() for sc in self.connections() ]
        prov_confirmed_defs , provision_done_defs = zip(*defs) # first is for confirmation, second is for link up
        #defs = [ sc.provision() for sc in self.connections() ]

        dl = defer.DeferredList(provision_done_defs, consumeErrors=True)
        #dl = defer.DeferredList(defs, consumeErrors=True)
        dl.addCallback(provisionComplete)
        return dl


    def release(self):

        def connectionReleased(results):
            successes = [ r[0] for r in results ]
            if all(successes):
                self.state.switchState(state.SCHEDULED)
                if len(results) > 1:
                    log.msg('Connection %s and all sub connections(%i) released' % (self.connection_id, len(results)-1), system=LOG_SYSTEM)
                self.scheduler.scheduleTransition(self.service_parameters.end_time, lambda s : self.state.switchState(state.TERMINATED), state.TERMINATED)
                self.eventDispatch(registry.RELEASE_RESPONSE, True, self)

            else:
                error_msg = self._buildErrorMessage(results, 'releases')
                err = error.ReleaseError(error_msg)
                f = failure.Failure(err)
                self.eventDispatch(registry.RELEASE_RESPONSE, False, f)

        self.state.switchState(state.RELEASING)
        self.scheduler.cancelTransition() # cancel any pending scheduled switch

        defs = []
        for sc in self.connections():
            d = sc.release()
            defs.append(d)

        dl = defer.DeferredList(defs, consumeErrors=True)
        dl.addCallback(connectionReleased)
        return dl


    def terminate(self):

        def connectionTerminated(results):
            successes = [ r[0] for r in results ]
            if all(successes):
                self.state.switchState(state.TERMINATED)
                if len(successes) > 1:
                    log.msg('Connection %s and all sub connections(%i) terminated' % (self.connection_id, len(results)-1), system=LOG_SYSTEM)
                self.eventDispatch(registry.TERMINATE_RESPONSE, True, self)

            else:
                error_msg = self._buildErrorMessage(results, 'terminates')
                err = error.TerminateError(error_msg)
                f = failure.Failure(err)
                self.eventDispatch(registry.TERMINATE_RESPONSE, False, f)

        self.state.switchState(state.TERMINATING)
        self.scheduler.cancelTransition() # cancel any pending scheduled switch

        defs = []
        for sc in self.connections():
            d = sc.terminate()
            defs.append(d)

        dl = defer.DeferredList(defs, consumeErrors=True)
        dl.addCallback(connectionTerminated)
        return dl

