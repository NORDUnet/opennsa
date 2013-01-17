"""
Connection abstraction.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

from twisted.python import log, failure
from twisted.internet import defer

from opennsa import error, nsa, state, registry
from opennsa.backends.common import scheduler



LOG_SYSTEM = 'opennsa.Connection'



def connPath(conn):
    """
    Utility function for getting a string with the source and dest STP of connection.
    """
    source_stp, dest_stp = conn.stps()
    return '<%s:%s--%s:%s>' % (source_stp.network, source_stp.endpoint, dest_stp.network, dest_stp.endpoint)



class SubConnection:

    def __init__(self, service_registry, requester_nsa, provider_nsa, parent_connection, connection_id, source_stp, dest_stp, service_parameters):
        self.service_registry   = service_registry
        self.requester_nsa      = requester_nsa # this the identity of the current nsa
        self.provider_nsa       = provider_nsa

        self.parent_connection  = parent_connection
        self.connection_id      = connection_id
        self.source_stp         = source_stp
        self.dest_stp           = dest_stp
        self.service_parameters = service_parameters

        self.session_security_attr = None
        self.client_system = registry.NSI1_CLIENT # this one is temporary


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
                                                    self.service_parameters.bandwidth,
                                                    directionality=self.service_parameters.directionality)

        reserve = self.service_registry.getHandler(registry.RESERVE, self.client_system)
        d = reserve(self.requester_nsa, self.provider_nsa, self.session_security_attr,
                    self.parent_connection.global_reservation_id, self.parent_connection.description, self.connection_id, sub_service_params)
        d.addCallback(reserveDone)
        return d


    def terminate(self):

        def terminateDone(int_res_id):
            log.msg('Remote connection %s via %s terminated' % (connPath(self), self.provider_nsa), debug=True, system=LOG_SYSTEM)
            return self

        terminate = self.service_registry.getHandler(registry.TERMINATE, self.client_system)
        d = terminate(self.requester_nsa, self.provider_nsa, self.session_security_attr, self.connection_id)
        d.addCallback(terminateDone)
        return d


    def provision(self):

        def provisionDone(int_res_id):
            log.msg('Remote connection %s via %s provisioned' % (connPath(self), self.provider_nsa), debug=True, system=LOG_SYSTEM)
            return self

        provision = self.service_registry.getHandler(registry.PROVISION, self.client_system)
        d = provision(self.requester_nsa, self.provider_nsa, self.session_security_attr, self.connection_id)
        d.addCallback(provisionDone)
        return defer.succeed(None), d


    def release(self):

        def releaseDone(int_res_id):
            log.msg('Remote connection %s via %s released' % (connPath(self), self.provider_nsa), debug=True, system=LOG_SYSTEM)
            return self

        release = self.service_registry.getHandler(registry.RELEASE, self.client_system)
        d = release(self.requester_nsa, self.provider_nsa, self.session_security_attr, self.connection_id)
        d.addCallback(releaseDone)
        return d



class Connection:

    def __init__(self, service_registry, requester_nsa, connection_id, source_stp, dest_stp, service_parameters=None, global_reservation_id=None, description=None):
        self.state                      = state.NSI2StateMachine()
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


    def _createAggregateFailure(self, results, action, default_error=error.InternalServerError):

        # need to handle multi-errors better, but infrastructure isn't there yet
        failures = [ conn for success,conn in results if not success ]
        if len(failures) == 0:
            # not supposed to happen
            err = failure.Failure( error.InternalServerError('_createAggregateFailure called with no failures') )
            log.err(err)
        if len(results) == 1 and len(failures) == 1:
            err = failures[0]
        else:
            error_msg = self._buildErrorMessage(results, action)
            err = failure.Failure( default_error(error_msg) )

        return err


    def reserve(self):

        def scheduled(st):
            self.state.scheduled()
            # not sure if something (or what) should be scheduled here
            #self.scheduler.scheduleTransition(self.service_parameters.end_time, self.state.terminatedEndtime, state.TERMINATED_ENDTIME)
            return self


        def reserveRequestsDone(results):
            successes = [ r[0] for r in results ]
            if all(successes):
                self.state.reserved()
                log.msg('Connection %s: Reserve succeeded' % self.connection_id, system=LOG_SYSTEM)
                self.scheduler.scheduleTransition(self.service_parameters.start_time, scheduled, state.SCHEDULED)
                return self

            else:
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
                dl.addCallback( self.state.terminatedFailed )

                err = self._createAggregateFailure(results, 'reservations', error.ConnectionCreateError)
                return err


        self.state.reserving()

        defs = [ defer.maybeDeferred(sc.reserve) for sc in self.connections() ]

        dl = defer.DeferredList(defs, consumeErrors=True)
        dl.addCallback(reserveRequestsDone) # never errbacks
        return dl


    def provision(self):

        def provisionComplete(results):
            successes = [ r[0] for r in results ]
            if all(successes):
                self.state.provisioned()
                # not sure if we should really schedule anything here
                #self.scheduler.scheduleTransition(self.service_parameters.end_time, self.state.terminatedEndtime, state.TERMINATED_ENDTIME)
                return self

            else:
                # at least one provision failed, provisioned connections should be released
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
                dl.addCallback( self.state.scheduled )

                def releaseDone(_):
                    err = self._createAggregateFailure(results, 'provisions', error.ProvisionError)
                    return err

                dl.addCallback(releaseDone)

        # --
        self.state.provisioning()
        self.scheduler.cancelTransition()
        defs = [ defer.maybeDeferred(sc.provision) for sc in self.connections() ]
        dl = defer.DeferredList(defs, consumeErrors=True)
        dl.addCallback(provisionComplete)
        return dl


    def release(self):

        def connectionReleased(results):
            successes = [ r[0] for r in results ]
            if all(successes):
                self.state.scheduled()
                if len(results) > 1:
                    log.msg('Connection %s and all sub connections(%i) released' % (self.connection_id, len(results)-1), system=LOG_SYSTEM)
                # unsure, if anything should be scheduled here
                #self.scheduler.scheduleTransition(self.service_parameters.end_time, self.state.terminatedEndtime, state.TERMINATED_ENDTIME)
                return self

            else:
                err = self._createAggregateFailure(results, 'releases', error.ReleaseError)
                return err

        self.state.releasing()
        self.scheduler.cancelTransition()

        defs = [ defer.maybeDeferred(sc.release) for sc in self.connections() ]
        dl = defer.DeferredList(defs, consumeErrors=True)
        dl.addCallback(connectionReleased)
        return dl


    def terminate(self):

        def connectionTerminated(results):
            successes = [ r[0] for r in results ]
            if all(successes):
                self.state.terminatedRequest()
                if len(successes) == len(results):
                    log.msg('Connection %s: All sub connections(%i) terminated' % (self.connection_id, len(results)-1), system=LOG_SYSTEM)
                else:
                    log.msg('Connection %s. Only %i of %i connections successfully terminated' % (self.connection_id, len(successes), len(results)), system=LOG_SYSTEM)
                return self
            else:
                err = self._createAggregateFailure(results, 'terminates', error.TerminateError)
                return err

        if self.state.isTerminated():
            return self

        self.state.terminating()
        self.scheduler.cancelTransition()

        defs = [ defer.maybeDeferred(sc.terminate) for sc in self.connections() ]
        dl = defer.DeferredList(defs, consumeErrors=True)
        dl.addCallback(connectionTerminated)
        return dl

