"""
Connection abstraction.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import datetime

from twisted.python import log, failure
from twisted.internet import defer

from opennsa import error, nsa, state
from opennsa.backends.common import scheduler



LOG_SYSTEM = 'opennsa.Connection'



def connPath(conn):
    """
    Utility function for getting a string with the source and dest STP of connection.
    """
    source_stp, dest_stp = conn.stps()
    return '<%s:%s--%s:%s>' % (source_stp.network, source_stp.endpoint, dest_stp.network, dest_stp.endpoint)



class SubConnection:

    def __init__(self, parent_connection, connection_id, nsa, source_stp, dest_stp, service_parameters, proxy):
        self.parent_connection  = parent_connection
        self.connection_id      = connection_id
        self.nsa                = nsa
        self.source_stp         = source_stp
        self.dest_stp           = dest_stp
        self.service_parameters = service_parameters

        self.state = state.ConnectionState()

        # the one should not be persistent, but should be set when re-created at startup
        self.proxy = proxy


    def curator(self):
        return self.nsa.identity


    def stps(self):
        return self.source_stp, self.dest_stp


    def reserve(self):

        def reserveDone(int_res_id):
            log.msg('Sub-connection for (%s -> %s) via %s reserved' % (self.source_stp.endpoint, self.dest_stp.endpoint, self.nsa), system=LOG_SYSTEM)
            self.state.switchState(state.RESERVED)
            return self

        def reserveFailed(err):
            self.state.switchState(state.TERMINATED)
            return err

        sub_service_params  = nsa.ServiceParameters(self.service_parameters.start_time,
                                                    self.service_parameters.end_time,
                                                    self.source_stp,
                                                    self.dest_stp,
                                                    directionality=self.service_parameters.directionality,
                                                    bandwidth=self.service_parameters.bandwidth)

        self.state.switchState(state.RESERVING)
        d = self.proxy.reserve(self.nsa, None, self.parent_connection.global_reservation_id, self.parent_connection.description, self.connection_id, sub_service_params)
        d.addCallbacks(reserveDone, reserveFailed)
        return d


    def terminate(self):

        def terminateDone(_):
            self.state.switchState(state.TERMINATED)
            return self

        def terminateFailed(err):
            self.state.switchState(state.TERMINATED)
            return err

        self.state.switchState(state.TERMINATING)
        d = self.proxy.terminate(self.nsa, None, self.connection_id)
        d.addCallbacks(terminateDone, terminateFailed)
        return d


    def provision(self):

        def provisionDone(conn_id):
            assert conn_id == self.connection_id
            self.state.switchState(state.PROVISIONED)
            return self

        def provisionFailed(err):
            self.state.switchState(state.TERMINATED)
            return err

        self.state.switchState(state.PROVISIONING)
        d = self.proxy.provision(self.nsa, None, self.connection_id)
        d.addCallbacks(provisionDone, provisionFailed)
        return d


    def release(self):

        def releaseDone(conn_id):
            assert conn_id == self.connection_id
            self.state.switchState(state.RESERVED)
            return self

        def releaseFailed(err):
            self.state.switchState(state.TERMINATED)
            return err

        self.state.switchState(state.RELEASING)
        d = self.proxy.release(self.nsa, None, self.connection_id)
        d.addCallbacks(releaseDone, releaseFailed)
        return d



class Connection:

    def __init__(self, requester_nsa, connection_id, source_stp, dest_stp, service_parameters=None, global_reservation_id=None, description=None):
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


    def connections(self):
        return self.sub_connections


    def reserve(self):

        def reserveRequestsDone(results):
            successes = [ r[0] for r in results ]
            if all(successes):
                self.state.switchState(state.RESERVED)
                self.scheduler.scheduleTransition(self.service_parameters.start_time, self.state.switchState, state.SCHEDULED)
                return self

            else:
                # at least one reservation failed
                self.state.switchState(state.CLEANING)
                # log the failures in an understandable way
                failures = [ (conn, f) for (success, f), conn in zip(results, self.connections()) if success is False ]
                failure_msgs = [ conn.curator() + ' ' + connPath(conn) + ' ' + f.getErrorMessage() for (conn, f) in failures ]
                log.msg('Connection %s: %i/%i reservations failed.' % (self.connection_id, len(failures), len(results)), system=LOG_SYSTEM)
                for msg in failure_msgs:
                    log.msg('* Failure: ' + msg, system=LOG_SYSTEM)

                # build the error message to send back
                if len(results) == 1:
                    # only one connection, we just return the plain failure
                    error_msg = failures[0][1].getErrorMessage()
                else:
                    # multiple failures, here we build a more complicated error string
                    error_msg = '%i/%i reservations failed: %s' % (len(failures), len(results), '. '.join(failure_msgs))

                # terminate non-failed connections
                # currently we don't try and be too clever about cleaning, just do it, and switch state
                defs = []
                reserved_connections = [ conn for success,conn in results if success ]
                for rc in reserved_connections:
                    d = rc.terminate()
                    d.addCallbacks(
                        lambda c : log.msg('Succesfully terminated sub-connection after partial reservation failure %s %s' % (c.curator(), connPath(c)) , system=LOG_SYSTEM),
                        lambda f : log.msg('Error terminating connection after partial-reservation failure: %s' % str(f), system=LOG_SYSTEM)
                    )
                    defs.append(d)
                dl = defer.DeferredList(defs)
                dl.addCallback(lambda _ : self.state.switchState(state.TERMINATED) )

                return defer.fail( error.ReserveError(error_msg) )


        self.state.switchState(state.RESERVING)

        defs = [ sc.reserve() for sc in self.connections() ]

        dl = defer.DeferredList(defs, consumeErrors=True)
        dl.addCallback(reserveRequestsDone) # never errbacks
        return dl


    def provision(self):

        def provisioned(_):
            # we cannot switch directly from sheduled/auto-provision to provisioned,
            # but an aggregate state cannot really be in provisioning (at least not in OpenNSA)
            self.state.switchState(state.PROVISIONING)
            self.state.switchState(state.PROVISIONED)
            self.scheduler.scheduleTransition(self.service_parameters.end_time, lambda _ : self.terminate(), state.TERMINATING)

        def provisionComplete(results):
            successes = [ r[0] for r in results ]
            if all(successes):
                dt_now = datetime.datetime.utcnow()
                if self.service_parameters.start_time <= dt_now:
                    provisioned(state.PROVISIONING)
                else:
                    self.scheduler.scheduleTransition(self.service_parameters.start_time, provisioned, state.PROVISIONING)
                return self

            else:
                # at least one provision failed
                failures = [ f for success, f in results if success is False ]
                failure_msg = ', '.join( [ f.getErrorMessage() for f in failures ] )
                error_msg = 'Provision failure. %i/%i connections failed. Reasons: %s.' % (len(failures), len(results), failure_msg)
                log.msg(error_msg, system=LOG_SYSTEM)
                # not sure what state should be used here...
                #self.state.switchState(state.RELEASING)

                # release provisioned connections
                provisioned_connections = [ conn for success,conn in results if success ]
                for pc in provisioned_connections:
                    d = pc.terminate()
                    d.addCallbacks(
                        lambda c : log.msg('Succesfully released sub-connection after partial provision failure (%s)' % str(c), system=LOG_SYSTEM),
                        lambda f : log.msg('Error releasing connection after partial provision failure: %s' % str(f), system=LOG_SYSTEM)
                    )
                    defs.append(d)
                dl = defer.DeferredList(defs)
                dl.addCallback(lambda _ : self.state.switchState(state.SCHEDULED) )

        # --

        # switch state to auto provision so we know that the connection be be provisioned before cancelling any transition
        self.state.switchState(state.AUTO_PROVISION)
        self.scheduler.cancelTransition() # cancel any pending scheduled switch

        defs = []
        for sc in self.connections():
            d = sc.provision()
            defs.append(d)

        dl = defer.DeferredList(defs, consumeErrors=True)
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
                return self
            if any(successes):
                self.state.switchState(state.TERMINATED)
                raise error.ReleaseError('Release partially failed (may require manual cleanup)')
            else:
                self.state.switchState(state.TERMINATED)
                err = error.ReleaseError('Release failed for all local/sub connection')
                return failure.Failure(err)

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
                return self
            if any(successes):
                self.state.switchState(state.TERMINATED)
                err = error.TerminateError('Cancel partially failed (may require manual cleanup)')
                return failure.Failure(err)
            else:
                self.state.switchState(state.TERMINATED)
                err = error.TerminateError('Cancel failed for all local/sub connections')
                return failure.Failure(err)

        self.state.switchState(state.TERMINATING)
        self.scheduler.cancelTransition() # cancel any pending scheduled switch

        defs = []
        for sc in self.connections():
            d = sc.terminate()
            defs.append(d)

        dl = defer.DeferredList(defs, consumeErrors=True)
        dl.addCallback(connectionTerminated)
        return dl

