"""
Connection abstraction.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""


from opennsa import error



# connection states
RESERVING           = 'RESERVING'
RESERVED            = 'RESERVED'
RESERVE_FAILED      = 'RESERVE_FAILED'

PROVISIONING        = 'PROVISIONING'
PROVISIONED         = 'PROVISIONED'
PROVISION_FAILED    = 'PROVISION_FAILED'

RELEASING           = 'RELEASING'
RELEASE_FAILED      = 'RELEASE_FAILED'

CANCELLING          = 'CANCELLING'
CANCELLED           = 'CANCELLED'
CANCEL_FAILED       = 'CANCEL_FAILED'

# allowed state transitions
TRANSITIONS = {
    RESERVING       : [ RESERVED,     RESERVE_FAILED    ],
    RESERVED        : [ PROVISIONING, CANCELLING         ],
    PROVISIONING    : [ PROVISIONED,  PROVISION_FAILED  ],
    PROVISIONED     : [ RELEASING                       ],
    RELEASING       : [ RESERVED,     RELEASE_FAILED    ],
    CANCELLING      : [ CANCELLED,    CANCEL_FAILED     ]
}



class ConnectionState:

    def __init__(self, state=RESERVING):
        self._state = state


    def state(self):
        return self._state


    def switchState(self, new_state):
        if new_state in TRANSITIONS[self._state]:
            self._state = new_state
        else:
            raise error.ConnectionStateTransitionError('Transition from state %s to %s not allowed' % (self._state, new_state))



class SubConnection(ConnectionState):

    def __init__(self, source_stp, dest_stp, network, connection_id, proxy=None):
        ConnectionState.__init__(self)
        self.source_stp = source_stp
        self.dest_stp   = dest_stp
        self.network    = network
        self.connection_id = connection_id

        # the one should not be persistent, but should be set when re-created at startup
        self._proxy = proxy


    def cancelReservation(self):

        assert self._proxy is not None, 'Proxy not set for SubConnection, cannot invoke method'

        def cancelDone(_):
            self.switchState(CANCELLED)
            return self

        def cancelFailed(err):
            self.switchState(CANCEL_FAILED)
            return err

        self.switchState(CANCELLING)
        d = self._proxy.cancelReservation(self.network, self.connection_id, None)
        d.addCallbacks(cancelDone, cancelFailed)
        return d


    def provision(self):

        assert self._proxy is not None, 'Proxy not set for SubConnection, cannot invoke method'

        def provisionDone(conn_id):
            assert conn_id == self.connection_id
            self.switchState(PROVISIONED)
            return self

        def provisionFailed(err):
            self.switchState(PROVISION_FAILED)
            return err

        self.switchState(PROVISIONING)
        d = self._proxy.provision(self.network, self.connection_id, None)
        d.addCallbacks(provisionDone, provisionFailed)
        return d


    def releaseProvision(self):

        assert self._proxy is not None, 'Proxy not set for SubConnection, cannot invoke method'

        def releaseDone(conn_id):
            assert conn_id == self.connection_id
            self.switchState(RESERVED)
            return self

        def releaseFailed(err):
            self.switchState(RELEASE_FAILED)
            return err

        self.switchState(RELEASING)
        d = self._proxy.releaseProvision(self.network, self.connection_id, None)
        d.addCallbacks(releaseDone, releaseFailed)
        return d



class LocalConnection(ConnectionState):

    def __init__(self, source_endpoint, dest_endpoint, internal_reservation_id, internal_connection_id=None, backend=None):
        ConnectionState.__init__(self)
        self.source_endpoint            = source_endpoint
        self.dest_endpoint              = dest_endpoint
        self.internal_reservation_id    = internal_reservation_id
        self.internal_connection_id     = internal_connection_id # pretty much never available at creation

        # the one should not be persistent, but should be set when re-created at startup
        self._backend = backend


    def cancelReservation(self):

        assert self._backend is not None, 'Backend not set for LocalConnection, cannot invoke method'

        def cancelDone(_):
            self.switchState(CANCELLED)
            return self

        def cancelFailed(err):
            self.switchState(CANCEL_FAILED)
            return err

        self.switchState(CANCELLING)
        d = self._backend.cancelReservation(self.internal_reservation_id)
        d.addCallbacks(cancelDone, cancelFailed)
        return d


    def provision(self):

        assert self._backend is not None, 'Backend not set for LocalConnection, cannot invoke method'

        def provisionDone(int_conn_id):
            self.internal_connection_id = int_conn_id
            self.switchState(PROVISIONED)
            return self

        def provisionFailed(err):
            self.switchState(PROVISION_FAILED)
            return err

        self.switchState(PROVISIONING)
        d = self._backend.provision(self.internal_reservation_id)
        d.addCallbacks(provisionDone, provisionFailed)
        return d


    def releaseProvision(self):

        assert self._backend is not None, 'Backend not set for LocalConnection, cannot invoke method'

        def releaseDone(int_res_id):
            self.internal_reservation_id = int_res_id
            self.internal_connection_id = None
            self.switchState(RESERVED)
            return self

        def releaseFailed(err):
            self.switchState(RELEASE_FAILED)
            return err

        self.switchState(RELEASING)
        d = self._backend.releaseProvision(self.internal_connection_id)
        d.addCallbacks(releaseDone, releaseFailed)
        return d



class Connection(ConnectionState):

    def __init__(self, connection_id, source_stp, dest_stp, local_connection, global_reservation_id=None, sub_connections=None):
        ConnectionState.__init__(self)
        self.connection_id              = connection_id
        self.local_connection           = local_connection
        self.source_stp                 = source_stp
        self.dest_stp                   = dest_stp
        self.local_connection           = local_connection
        self.global_reservation_id      = global_reservation_id
        self.sub_connections            = sub_connections or []


    def hasLocalConnection(self):
        return self.local_connection is not None


    def connections(self):
        if self.local_connection is not None:
            return [ self.local_connection ] + self.sub_connections
        else:
            return self.sub_connections

