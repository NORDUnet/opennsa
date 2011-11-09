"""
Connection abstraction.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""


from twisted.python import log, failure
from twisted.internet import defer

from opennsa import error, nsa, state



LOG_SYSTEM = 'opennsa.Connection'


class SubConnection:

    def __init__(self, parent_connection, connection_id, network, source_stp, dest_stp, service_parameters, proxy=None):
        self.state = state.ConnectionState()
        self.parent_connection  = parent_connection
        self.connection_id      = connection_id
        self.network            = network
        self.source_stp         = source_stp
        self.dest_stp           = dest_stp
        self.service_parameters = service_parameters

        # the one should not be persistent, but should be set when re-created at startup
        self._proxy = proxy


    def stps(self):
        return self.source_stp, self.dest_stp


    def reserve(self):

        assert self._proxy is not None, 'Proxy not set for SubConnection, cannot invoke method'

        def reserveDone(int_res_id):
            log.msg('Sub-connection for network %s (%s -> %s) reserved' % (self.network, self.source_stp.endpoint, self.dest_stp.endpoint), system=LOG_SYSTEM)
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
        d = self._proxy.reserve(self.network, None, self.parent_connection.global_reservation_id, self.parent_connection.description, self.connection_id, sub_service_params)
        d.addCallbacks(reserveDone, reserveFailed)
        return d


    def terminate(self):

        assert self._proxy is not None, 'Proxy not set for SubConnection, cannot invoke method'

        def terminateDone(_):
            self.state.switchState(state.TERMINATED)
            return self

        def terminateFailed(err):
            self.state.switchState(state.TERMINATED)
            return err

        self.state.switchState(state.TERMINATING)
        d = self._proxy.terminate(self.network, None, self.connection_id)
        d.addCallbacks(terminateDone, terminateFailed)
        return d


    def provision(self):

        assert self._proxy is not None, 'Proxy not set for SubConnection, cannot invoke method'

        def provisionDone(conn_id):
            assert conn_id == self.connection_id
            self.state.switchState(state.PROVISIONED)
            return self

        def provisionFailed(err):
            self.state.switchState(state.TERMINATED)
            return err

        self.state.switchState(state.PROVISIONING)
        d = self._proxy.provision(self.network, None, self.connection_id)
        d.addCallbacks(provisionDone, provisionFailed)
        return d


    def release(self):

        assert self._proxy is not None, 'Proxy not set for SubConnection, cannot invoke method'

        def releaseDone(conn_id):
            assert conn_id == self.connection_id
            self.state.switchState(state.RESERVED)
            return self

        def releaseFailed(err):
            self.state.switchState(state.TERMINATED)
            return err

        self.state.switchState(state.RELEASING)
        d = self._proxy.release(self.network, None, self.connection_id)
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
        self.local_connection           = None
        self.sub_connections            = []


    def hasLocalConnection(self):
        return self.local_connection is not None


    def connections(self):
        if self.local_connection is not None:
            return [ self.local_connection ] + self.sub_connections
        else:
            return self.sub_connections


    def reserve(self):

        def reserveRequestsDone(results):
            successes = [ r[0] for r in results ]
            if all(successes):
                self.state.switchState(state.RESERVED)
                return self
            else:
                self.state.switchState(state.TERMINATED)
                if any(successes):
                    failure_msg = ' # '.join( [ f.getErrorMessage() for success,f in results if success is False ] )
                    log.msg('Partial failure in reserve, attempting termination of reserved sub-connections (%s)' % failure_msg, system=LOG_SYSTEM)
                    error_msg = 'Partial failure in reserve, attempting termination of reserved sub-connections (%s)' % failure_msg
                    # terminate non-failed connections
                    reserved_connections = [ conn for success,conn in results if success ]
                    for rc in reserved_connections:
                        d = rc.terminate()
                        d.addCallbacks(
                            lambda c : log.msg('Succesfully terminated sub-connection after partial reservation failure (%s)' % str(c), system=LOG_SYSTEM),
                            lambda f : log.msg('Error terminating connection after partial-reservation failure: %s' % str(f), system=LOG_SYSTEM)
                        )
                else:
                    failure_msg = ' # '.join( [ f.getErrorMessage() for _,f in results ] )
                    error_msg = 'Reservation failed for all local/sub connections (%s)' % failure_msg
                return defer.fail( error.ReserveError(error_msg) )

        self.state.switchState(state.RESERVING)

        defs = []
        for sc in self.connections():
            d = sc.reserve()
            defs.append(d)

        dl = defer.DeferredList(defs, consumeErrors=True)
        dl.addCallbacks(reserveRequestsDone) # never errbacks
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

        defs = []
        for sc in self.connections():
            d = sc.terminate()
            defs.append(d)

        dl = defer.DeferredList(defs, consumeErrors=True)
        dl.addCallback(connectionTerminated)
        return dl


    def provision(self):

        def provisionComplete(results):
            successes = [ r[0] for r in results ]
            if all(successes):
                self.state.switchState(state.PROVISIONED)
                if len(results) > 1:
                    log.msg('Connection %s and all sub connections(%i) provisioned' % (self.connection_id, len(results)-1), system=LOG_SYSTEM)
                return self
            if any(successes):
                self.state.switchState(state.TERMINATED)
                err = error.ProvisionError('Provision partially failed (may require manual cleanup)')
                return failure.Failure(err)
            else:
                self.state.switchState(state.TERMINATED)
                err = error.ProvisionError('Provision failed for all local/sub connections')
                return failure.Failure(err)

        self.state.switchState(state.PROVISIONING)

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
                return self
            if any(successes):
                self.state.switchState(state.TERMINATED)
                raise error.ReleaseError('Release partially failed (may require manual cleanup)')
            else:
                self.state.switchState(state.TERMINATED)
                err = error.ReleaseError('Release failed for all local/sub connection')
                return failure.Failure(err)

        self.state.switchState(state.RELEASING)

        defs = []
        for sc in self.connections():
            d = sc.release()
            defs.append(d)

        dl = defer.DeferredList(defs, consumeErrors=True)
        dl.addCallback(connectionReleased)
        return dl

