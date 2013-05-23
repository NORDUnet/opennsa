"""
Connection abstraction.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""
import string
import random
import datetime

from twisted.python import log, failure
from twisted.internet import defer

from opennsa import error, nsa, state, registry, database



LOG_SYSTEM = 'opennsa.Aggregator'



#def connPath(conn):
#    """
#    Utility function for getting a string with the source and dest STP of connection.
#    """
#    source_stp, dest_stp = conn.stps()
#    return '<%s:%s--%s:%s>' % (source_stp.network, source_stp.endpoint, dest_stp.network, dest_stp.endpoint)



#class SubConnection:
#
#    def __init__(self, service_registry, requester_nsa, provider_nsa, parent_connection, connection_id, source_stp, dest_stp, service_parameters):
#        self.service_registry   = service_registry
#        self.requester_nsa      = requester_nsa # this the identity of the current nsa
#        self.provider_nsa       = provider_nsa
#
#        self.parent_connection  = parent_connection
#        self.connection_id      = connection_id
#        self.source_stp         = source_stp
#        self.dest_stp           = dest_stp
#        self.service_parameters = service_parameters
#
#        self.session_security_attr = None
#
#
#    def curator(self):
#        return self.provider_nsa.identity
#
#
#    def stps(self):
#        return self.source_stp, self.dest_stp
#
#
#    def reserve(self):
#
#        def reserveDone(int_res_id):
#            log.msg('Remote connection %s via %s reserved' % (connPath(self), self.provider_nsa), debug=True, system=LOG_SYSTEM)
#            return self
#
#        sub_service_params  = nsa.ServiceParameters(self.service_parameters.start_time,
#                                                    self.service_parameters.end_time,
#                                                    self.source_stp,
#                                                    self.dest_stp,
#                                                    self.service_parameters.bandwidth,
#                                                    directionality=self.service_parameters.directionality)
#
#        reserve = self.service_registry.getHandler(registry.RESERVE, self.client_system)
#        d = reserve(self.requester_nsa, self.provider_nsa, self.session_security_attr,
#                    self.parent_connection.global_reservation_id, self.parent_connection.description, self.connection_id, sub_service_params)
#        d.addCallback(reserveDone)
#        return d
#
#
#    def terminate(self):
#
#        def terminateDone(int_res_id):
#            log.msg('Remote connection %s via %s terminated' % (connPath(self), self.provider_nsa), debug=True, system=LOG_SYSTEM)
#            return self
#
#        terminate = self.service_registry.getHandler(registry.TERMINATE, self.client_system)
#        d = terminate(self.requester_nsa, self.provider_nsa, self.session_security_attr, self.connection_id)
#        d.addCallback(terminateDone)
#        return d
#
#
#    def provision(self):
#
#        def provisionDone(int_res_id):
#            log.msg('Remote connection %s via %s provisioned' % (connPath(self), self.provider_nsa), debug=True, system=LOG_SYSTEM)
#            return self
#
#        provision = self.service_registry.getHandler(registry.PROVISION, self.client_system)
#        d = provision(self.requester_nsa, self.provider_nsa, self.session_security_attr, self.connection_id)
#        d.addCallback(provisionDone)
#        return defer.succeed(None), d
#
#
#    def release(self):
#
#        def releaseDone(int_res_id):
#            log.msg('Remote connection %s via %s released' % (connPath(self), self.provider_nsa), debug=True, system=LOG_SYSTEM)
#            return self
#
#        release = self.service_registry.getHandler(registry.RELEASE, self.client_system)
#        d = release(self.requester_nsa, self.provider_nsa, self.session_security_attr, self.connection_id)
#        d.addCallback(releaseDone)
#        return d



#class Connection:

#    def __init__(self, service_registry, requester_nsa, connection_id, source_stp, dest_stp, service_parameters=None, global_reservation_id=None, description=None):
#        self.state                      = state.NSI2StateMachine()
#        self.requester_nsa              = requester_nsa
#        self.connection_id              = connection_id
#        self.source_stp                 = source_stp
#        self.dest_stp                   = dest_stp
#        self.service_parameters         = service_parameters
#        self.global_reservation_id      = global_reservation_id
#        self.description                = description
#        self.scheduler                  = scheduler.TransitionScheduler()
#        self.sub_connections            = []
#
#        self.subscriptions              = []
#        self.service_registry           = service_registry


#    def connections(self):
#        return self.sub_connections


def _buildErrorMessage(results, action):

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


def _createAggregateException(results, action, default_error=error.InternalServerError):

    # need to handle multi-errors better, but infrastructure isn't there yet
    failures = [ conn for success,conn in results if not success ]
    if len(failures) == 0:
        # not supposed to happen
        return error.InternalServerError('_createAggregateException called with no failures')
    if len(results) == 1 and len(failures) == 1:
        return failures[0]
    else:
        error_msg = _buildErrorMessage(results, action)
        return default_error(error_msg)


def _createAggregateFailure(results, action):

#    # need to handle multi-errors better, but infrastructure isn't there yet
#    failures = [ conn for success,conn in results if not success ]
#    if len(failures) == 0:
#        # not supposed to happen
#        err = failure.Failure( error.InternalServerError('_createAggregateFailure called with no failures') )
#        log.err(err)
#    if len(results) == 1 and len(failures) == 1:
#        err = failures[0]
#    else:
#        error_msg = self._buildErrorMessage(results, action)
#        err = failure.Failure( default_error(error_msg) )
#
#    return err
    err = _createAggregateException(results, action)
    return failure.Failure(err)



class Aggregator:

    def __init__(self, network, nsa_, topology, service_registry, parent_system):
        self.network = network
        self.nsa_ = nsa_
        self.topology = topology
        self.service_registry = service_registry
        self.parent_system = parent_system

        self.service_registry.registerEventHandler(registry.RESERVE,            self.reserve,           registry.NSI2_AGGREGATOR)
        self.service_registry.registerEventHandler(registry.RESERVE_COMMIT,     self.reserveCommit,     registry.NSI2_AGGREGATOR)
        self.service_registry.registerEventHandler(registry.RESERVE_ABORT,      self.reserveAbort,      registry.NSI2_AGGREGATOR)
        self.service_registry.registerEventHandler(registry.PROVISION,          self.provision,         registry.NSI2_AGGREGATOR)
        self.service_registry.registerEventHandler(registry.RELEASE,            self.release,           registry.NSI2_AGGREGATOR)
        self.service_registry.registerEventHandler(registry.TERMINATE,          self.terminate,         registry.NSI2_AGGREGATOR)

        self.service_registry.registerEventHandler(registry.DATA_PLANE_CHANGE,  self.dataPlaneChange,   registry.NSI2_AGGREGATOR)


    def getConnection(self, requester_nsa, connection_id):

        # need to do authz here

        def gotResult(connections):
            # we should get 0 or 1 here since connection id is unique
            if len(connections) == 0:
                return defer.fail( error.ConnectionNonExistentError('No connection with id %s' % connection_id) )
            return connections[0]

        d = database.ServiceConnection.findBy(connection_id=connection_id)
        d.addCallback(gotResult)
        return d


    @defer.inlineCallbacks
    def forAllSubConnections(self, conn, event):
        # do a certain event for all sub connection for a connection
        # only works for calls where handler args is: requester, provider, security_attrs, connection_id
        # this happens to be quite a lot though

        sub_connections = yield conn.SubConnections.get()

        defs = []

        for sc in sub_connections:
            cs = registry.NSI2_LOCAL if sc.provider_nsa == self.nsa_.urn() else registry.NSI2_REMOTE
            handler = self.service_registry.getHandler(event, cs)

            d = handler(self.nsa_, sc.provider_nsa, None, sc.connection_id)
            defs.append(d)

        defer.returnValue(defs)


    @defer.inlineCallbacks
    def reserve(self, requester_nsa, provider_nsa, session_security_attr, connection_id, global_reservation_id, description, service_params):

        log.msg('', system=LOG_SYSTEM)
        log.msg('Reserve request. NSA: %s. Connection ID: %s' % (requester_nsa, connection_id), system=LOG_SYSTEM)

        # rethink with modify
        if connection_id != None:
            connection_exists = yield database.ServiceConnection.exists(['connection_id = ?', connection_id])
            if connection_exists:
                raise error.ConnectionExistsError('Connection with id %s already exists' % connection_id)
            raise NotImplementedError('Cannot handly modification of existing connections yet')

        connection_id = 'NU-T' + ''.join( [ random.choice(string.hexdigits[:16]) for _ in range(12) ] )

        source_stp = service_params.source_stp
        dest_stp   = service_params.dest_stp

        # check that we know the networks
        self.topology.getNetwork(source_stp.network)
        self.topology.getNetwork(dest_stp.network)

        # if the link terminates at our network, check that ports exists
        if source_stp.network == self.network:
            self.topology.getNetwork(self.network).getPort(source_stp.port)
        if dest_stp.network == self.network:
            self.topology.getNetwork(self.network).getPort(dest_stp.port)

        if source_stp == dest_stp and source_stp.label.singleValue():
            raise error.TopologyError('Cannot connect STP %s to itself.' % source_stp)

        conn = database.ServiceConnection(connection_id=connection_id, revision=0, global_reservation_id=global_reservation_id, description=description,
                            requester_nsa=requester_nsa.urn(), reserve_time=datetime.datetime.utcnow(),
                            reservation_state=state.INITIAL, provision_state=state.SCHEDULED, activation_state=state.INACTIVE, lifecycle_state=state.INITIAL,
                            source_network=source_stp.network, source_port=source_stp.port, source_labels=source_stp.labels,
                            dest_network=dest_stp.network, dest_port=dest_stp.port, dest_labels=dest_stp.labels,
                            start_time=service_params.start_time, end_time=service_params.end_time, bandwidth=service_params.bandwidth)
        yield conn.save()

        # As STP Labels are only candidates as this point they will need to be changed later

#        def reserveResponse(result):
#            success = False if isinstance(result, failure.Failure) else True
#            if not success:
#                log.msg('Error reserving: %s' % result.getErrorMessage(), system=LOG_SYSTEM)
#            d = subscription.dispatchNotification(success, result, sub, self.service_registry)


    #    def reserveRequestsDone(results):
    #        successes = [ r[0] for r in results ]
    #        if all(successes):
    #            state.reserved(conn)
    #            log.msg('Connection %s: Reserve succeeded' % self.connection_id, system=LOG_SYSTEM)
    #            self.scheduler.scheduleTransition(self.service_parameters.start_time, scheduled, state.SCHEDULED)
    #            return self
    #
    #        else:
    #            # terminate non-failed connections
    #            # currently we don't try and be too clever about cleaning, just do it, and switch state
    #            defs = []
    #            reserved_connections = [ conn for success,conn in results if success ]
    #            for rc in reserved_connections:
    #                d = rc.terminate()
    #                d.addCallbacks(
    #                    lambda c : log.msg('Succesfully terminated sub connection after partial reservation failure %s %s' % (c.curator(), connPath(c)) , system=LOG_SYSTEM),
    #                    lambda f : log.msg('Error terminating connection after partial-reservation failure: %s' % str(f), system=LOG_SYSTEM)
    #                )
    #                defs.append(d)
    #            dl = defer.DeferredList(defs)
    #            dl.addCallback( self.state.terminatedFailed )
    #
    #            err = self._createAggregateFailure(results, 'reservations', error.ConnectionCreateError)
    #            return err

        yield state.reserveChecking(conn) # this also acts a lock

        if conn.source_network == self.network and conn.dest_network == self.network:
            path_info = ( conn.connection_id, self.network, conn.source_port, conn.source_labels, conn.dest_port, conn.dest_labels )
            log.msg('Connection %s: Local link creation: %s %s#%s -> %s#%s' % path_info, system=LOG_SYSTEM)
            paths = [ [ nsa.Link(self.network, conn.source_port, conn.dest_port, conn.source_labels, conn.dest_labels) ] ]

        else:
            # log about creation and the connection type
            path_info = ( conn.connection_id, conn.source_network, conn.source_port, conn.dest_network, conn.dest_port, conn.nsa)
            log.msg('Connection %s: Aggregate path creation: %s:%s -> %s:%s (%s)' % path_info, system=LOG_SYSTEM)
            # making the connection is the same for all though :-)
            paths = self.topology.findPaths(source_stp, dest_stp)

            # error out if we could not find a path
            if not paths:
                error_msg = 'Could not find a path for route %s:%s -> %s:%s' % (source_stp.network, source_stp.port, dest_stp.network, dest_stp.port)
                log.msg(error_msg, system=LOG_SYSTEM)
                raise error.TopologyError(error_msg)

            paths.sort(key=lambda e : len(e.links()))

        selected_path = paths[0] # shortest path
        log.msg('Attempting to create path %s' % selected_path, system=LOG_SYSTEM)
        ## fixme, need to set end labels here

        defs = []
        for idx, link in enumerate(selected_path):

            ssp  = nsa.ServiceParameters(conn.start_time, conn.end_time,
                                         nsa.STP(link.network, link.src_port, labels=link.src_labels),
                                         nsa.STP(link.network, link.dst_port, labels=link.dst_labels),
                                         conn.bandwidth)

            cs = registry.NSI2_LOCAL if link.network == self.network else registry.NSI2_REMOTE
            reserve = self.service_registry.getHandler(registry.RESERVE, cs)
            link_provider_nsa = self.topology.getNetwork(self.network).managing_nsa

            d = reserve(self.nsa_, link_provider_nsa, None, conn.global_reservation_id, conn.description, None, ssp)

            @defer.inlineCallbacks
            def reserveDone(rig, link_provider_nsa, order_id):
                # need to collapse the end stps in Connection object
                global_reservation_id, description, connection_id, service_params = rig
                log.msg('Sub link %s via %s reserved' % (connection_id, link_provider_nsa), debug=True, system=LOG_SYSTEM)
                # should probably do some sanity checks here
                sp = service_params
                local_link = True if link_provider_nsa == self.nsa_ else False
                sc = database.SubConnection(provider_nsa=link_provider_nsa.urn(),
                                            connection_id=connection_id, local_link=local_link, revision=0, service_connection_id=conn.id, order_id=order_id,
                                            global_reservation_id=global_reservation_id, description=description,
                                            reservation_state=state.RESERVE_HELD, provision_state=state.SCHEDULED, activation_state=state.INACTIVE, lifecycle_state=state.INITIAL,
                                            source_network=sp.source_stp.network, source_port=sp.source_stp.port, source_labels=sp.source_stp.labels,
                                            dest_network=sp.dest_stp.network, dest_port=sp.dest_stp.port, dest_labels=sp.dest_stp.labels,
                                            start_time=sp.start_time.isoformat(), end_time=sp.end_time.isoformat(), bandwidth=sp.bandwidth)
                yield sc.save()
                defer.returnValue(sc)

            d.addCallback(reserveDone, link_provider_nsa, idx)
            defs.append(d)

        results = yield defer.DeferredList(defs, consumeErrors=True) # doesn't errback
        successes = [ r[0] for r in results ]

        if all(successes):
            yield state.reserveHeld(conn)
            log.msg('Connection %s: Reserve succeeded' % conn.connection_id, system=LOG_SYSTEM)
            defer.returnValue( (connection_id, global_reservation_id, description, service_params) )

        else:
            # terminate non-failed connections
            # currently we don't try and be too clever about cleaning, just do it, and switch state
            yield state.terminating(conn)
            defs = []
            reserved_connections = [ sc for success,sc in results if success ]
            for rc in reserved_connections:
                d = rc.terminate()
                d.addCallbacks(
                    lambda c : log.msg('Succesfully terminated sub connection after partial reservation failure %s %s' % (c.curator(), connPath(c)) , system=LOG_SYSTEM),
                    lambda f : log.msg('Error terminating connection after partial-reservation failure: %s' % str(f), system=LOG_SYSTEM)
                )
                defs.append(d)
            dl = defer.DeferredList(defs)
            yield dl
            yield state.terminated(conn)

            err = _createAggregateException(results, 'reservations', error.ConnectionCreateError)
            raise err




    @defer.inlineCallbacks
    def reserveCommit(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('ReserveCommit request. NSA: %s. Connection ID: %s' % (requester_nsa, connection_id), system=LOG_SYSTEM)

        conn = yield self.getConnection(requester_nsa, connection_id)

        if conn.lifecycle_state == state.TERMINATED:
            raise error.ConnectionGoneError('Connection %s has been terminated')

        yield state.reserveCommit(conn)

        defs = yield self.forAllSubConnections(conn, registry.RESERVE_COMMIT)
        results = yield defer.DeferredList(defs, consumeErrors=True)

        successes = [ r[0] for r in results ]
        if all(successes):
            log.msg('Connection %s: ReserveCommit succeeded' % conn.connection_id, system=LOG_SYSTEM)
            yield state.reserved(conn)
            defer.returnValue(connection_id)

        else:
            n_success = sum( [ 1 for s in successes if s ] )
            log.msg('Connection %s. Only %i of %i connections committed' % (self.connection_id, len(n_success), len(defs)), system=LOG_SYSTEM)
            raise self._createAggregateFailure(results, 'committed', error.ConnectionError)


    @defer.inlineCallbacks
    def reserveAbort(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('ReserveAbort request. NSA: %s. Connection ID: %s' % (requester_nsa, connection_id), system=LOG_SYSTEM)

        conn = yield self.getConnection(requester_nsa, connection_id)

        if conn.lifecycle_state == state.TERMINATED:
            raise error.ConnectionGoneError('Connection %s has been terminated')

        yield state.reserveAbort(conn)

        defs = yield self.forAllSubConnections(conn, registry.RESERVE_ABORT)
        results = yield defer.DeferredList(defs, consumeErrors=True)

        successes = [ r[0] for r in results ]
        if all(successes):
            log.msg('Connection %s: ReserveAbort succeeded' % conn.connection_id, system=LOG_SYSTEM)
            yield state.reserved(conn)
            defer.returnValue(connection_id)

        else:
            n_success = sum( [ 1 for s in successes if s ] )
            log.msg('Connection %s. Only %i of %i connections aborted' % (self.connection_id, len(n_success), len(defs)), system=LOG_SYSTEM)
            raise self._createAggregateFailure(results, 'aborted', error.ConnectionError)


    @defer.inlineCallbacks
    def provision(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('ReserveCommit request. NSA: %s. Connection ID: %s' % (requester_nsa, connection_id), system=LOG_SYSTEM)

        conn = yield self.getConnection(requester_nsa, connection_id)

        if conn.lifecycle_state == state.TERMINATED:
            raise error.ConnectionGoneError('Connection %s has been terminated')

        yield state.provisioning(conn)

        defs = yield self.forAllSubConnections(conn, registry.PROVISION)
        results = yield defer.DeferredList(defs, consumeErrors=True)

        successes = [ r[0] for r in results ]
        if all(successes):
            yield state.provisioned(conn)
            defer.returnValue(connection_id)

        else:
            n_success = sum( [ 1 for s in successes if s ] )
            log.msg('Connection %s. Only %i of %i connections successfully provision' % (self.connection_id, len(n_success), len(defs)), system=LOG_SYSTEM)
            raise self._createAggregateFailure(results, 'provision', error.ConnectionError)


    @defer.inlineCallbacks
    def release(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('Release request. NSA: %s. Connection ID: %s' % (requester_nsa, connection_id), system=LOG_SYSTEM)

        conn = yield self.getConnection(requester_nsa, connection_id)

        if conn.lifecycle_state == state.TERMINATED:
            raise error.ConnectionGoneError('Connection %s has been terminated')

        yield state.releasing(conn)

        defs = yield self.forAllSubConnections(conn, registry.RELEASE)
        results = yield defer.DeferredList(defs, consumeErrors=True)

        successes = [ r[0] for r in results ]
        if all(successes):
            log.msg('Connection %s: Release succeeded' % conn.connection_id, system=LOG_SYSTEM)
            yield state.scheduled(conn)
            defer.returnValue(connection_id)

        else:
            n_success = sum( [ 1 for s in successes if s ] )
            log.msg('Connection %s. Only %i of %i connections successfully provision' % (self.connection_id, len(n_success), len(defs)), system=LOG_SYSTEM)
            raise self._createAggregateFailure(results, 'provision', error.ConnectionError)


    @defer.inlineCallbacks
    def terminate(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('Terminate request. NSA: %s. Connection ID: %s' % (requester_nsa, connection_id), system=LOG_SYSTEM)

        conn = yield self.getConnection(requester_nsa, connection_id)

        if conn.lifecycle_state == state.TERMINATED:
            defer.returnValue(connection_id) # all good

        yield state.terminating(conn)

        defs = yield self.forAllSubConnections(conn, registry.TERMINATE)

        results = yield defer.DeferredList(defs, consumeErrors=True)
        successes = [ r[0] for r in results ]
        if all(successes):
            yield state.terminated(conn)
            log.msg('Connection %s: Terminate succeeded' % conn.connection_id, system=LOG_SYSTEM)
            log.msg('Connection %s: All sub connections(%i) terminated' % (conn.connection_id, len(defs)), system=LOG_SYSTEM)
        else:
            # we are now in an inconsistent state...
            n_success = sum( [ 1 for s in successes if s ] )
            log.msg('Connection %s. Only %i of %i connections successfully terminated' % (self.connection_id, len(n_success), len(defs)), system=LOG_SYSTEM)
            raise self._createAggregateFailure(results, 'terminate', error.ConnectionError)

        defer.returnValue(connection_id)

    # --

    @defer.inlineCallbacks
    def doActivate(self, conn):
        yield state.activating(conn)
        yield state.active(conn)
        data_plane_change = self.service_registry.getHandler(registry.DATA_PLANE_CHANGE, self.parent_system)
        dps = (True, conn.revision, True) # data plane status - active, version, version consistent
        data_plane_change(None, None, None, conn.connection_id, dps, datetime.datetime.utcnow())


    @defer.inlineCallbacks
    def doTeardown(self, conn):
        yield state.deactivating(conn)
        yield state.inactive(conn)
        data_plane_change = self.service_registry.getHandler(registry.DATA_PLANE_CHANGE, self.parent_system)
        dps = (False, conn.revision, True) # data plane status - active, version, version consistent
        data_plane_change(None, None, None, conn.connection_id, dps, datetime.datetime.utcnow())

    # --

    @defer.inlineCallbacks
    def dataPlaneChange(self, requester_nsa, provider_nsa, session_security_attr, connection_id, dps, timestamp):

        active, version, version_consistent = dps

        sub_conns_match = yield database.SubConnection.findBy(connection_id=connection_id)

        if len(sub_conns_match) == 0:
            log.msg('No subconnections with id %s found' % connection_id)
        elif len(sub_conns_match) == 1:

            conn = yield sub_conns_match[0].ServiceConnection.get()
            sub_conns = yield conn.SubConnections.get()

            if len(sub_conns) == 1:
                log.msg("than one sub connection for connection %s, notifying" % conn.connection_id)
                # assert that data plane came up...
                if active:
                    yield self.doActivate(conn)
                else:
                    yield self.doTeardown(conn)
            else:
                log.msg("more than one sub connection for connection %s" % conn.connection_id)

        else:
            log.msg('More than one subconnection with id %s found. Hmm..' % connection_id)

