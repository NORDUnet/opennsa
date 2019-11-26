"""
Connection abstraction.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""
import datetime

from zope.interface import implementer

from twisted.python import log
from twisted.internet import defer

from opennsa.interface import INSIProvider, INSIRequester
from opennsa import error, nsa, state, database, constants as cnt



LOG_SYSTEM = 'Aggregator'



def shortLabel(label):
    # create a log friendly string representation of a label
    if label is None: # it happens
        return ''

    if '}' in label.type_:
        name = label.type_.split('}',1)[1]
    elif '#' in label.type_:
        name = label.type_.split('#',1)[1]
    else:
        name = label.type_
    return name + '=' + label.labelValue()



def _logErrorResponse(err, connection_id, provider_nsa, action):

    log.msg('Connection %s: Error during %s request to %s.' % (connection_id, action, provider_nsa), system=LOG_SYSTEM)
    log.msg('Connection %s: Error message: %s' % (connection_id, err.getErrorMessage()), system=LOG_SYSTEM)
    log.msg('Trace:', system=LOG_SYSTEM)
    err.printTraceback()

    return err



def _createAggregateException(connection_id, action, results, provider_urns, default_error=error.InternalServerError):

    failures = [ conn for success,conn in results if not success ]

    if len(failures) == 0: # not supposed to happen
        return error.InternalServerError('_createAggregateException called with no failures')

    if len(failures) == 1:
        return failures[0]

    else: # multiple errors
        provider_failures = [ provider_urn + ': ' + f.getErrorMessage() for provider_urn, (success,f) in zip(provider_urns, results) if not success ]
        error_msg = '%i/%i %s failed:\n  %s' % (len(failures), len(results), action, '\n  '.join(provider_failures))
        return default_error(error_msg)



@implementer(INSIProvider)
@implementer(INSIRequester)
class Aggregator:

    def __init__(self, network, nsa_, network_topology, route_vectors, parent_requester, provider_registry, policies, plugin):
        self.network = network
        self.nsa_ = nsa_
        self.network_topology = network_topology
        self.route_vectors = route_vectors

        self.parent_requester   = parent_requester
        self.provider_registry  = provider_registry
        self.policies           = policies
        self.plugin             = plugin

        self.reservations       = {} # correlation_id -> info
        self.notification_id    = 0

        # db orm cache, needed to avoid concurrent updates stepping on each other
        self.db_connections = {}
        self.db_sub_connections = {}

        # these are for query recursive, due to nsi being extremely crappy design
        self.query_requests = {}
        self.query_calls = {}


    def getNotificationId(self):
        nid = self.notification_id
        self.notification_id += 1
        return nid


    def getProvider(self, nsi_agent_urn):
        return self.provider_registry.getProvider(nsi_agent_urn)


    def getConnection(self, connection_id):

        # need to do authz here

        def gotResult(connections):
            # we should get 0 or 1 here since connection id is unique
            if len(connections) == 0:
                return defer.fail( error.ConnectionNonExistentError('No connection with id %s' % connection_id) )
            self.db_connections[connection_id] = connections[0]
            return connections[0]

        if connection_id in self.db_connections:
            return defer.succeed(self.db_connections[connection_id])

        d = database.ServiceConnection.findBy(connection_id=connection_id)
        d.addCallback(gotResult)
        return d


    def getConnectionByKey(self, connection_key):

        def gotResult(connections):
            # we should get 0 or 1 here since connection id is unique
            if len(connections) == 0:
                return defer.fail( error.ConnectionNonExistentError('No connection with key %s' % connection_key) )
            conn = connections[0]
            return self.getConnection(conn.connection_id)

        d = database.ServiceConnection.findBy(id=connection_key)
        d.addCallback(gotResult)
        return d


    def getSubConnection(self, provider_nsa, connection_id):

        def gotResult(connections):
            # we should get 0 or 1 here since provider_nsa + connection id is unique
            if len(connections) == 0:
                return defer.fail( error.ConnectionNonExistentError('No sub connection with connection id %s at provider %s' % (connection_id, provider_nsa) ) )
            self.db_sub_connections[connection_id] = connections[0]
            return connections[0]

        if connection_id in self.db_sub_connections:
            return defer.succeed(self.db_sub_connections[connection_id])

        d = database.SubConnection.findBy(provider_nsa=provider_nsa, connection_id=connection_id)
        d.addCallback(gotResult)
        return d


    def getSubConnectionsByConnectionKey(self, service_connection_key):

        def gotResult(rows):
            def gotSubConns(results):
                if all( [ r[0] for r in results ] ):
                    return [ r[1] for r in results ]
                else:
                    return defer.fail( ValueError('Error retrieving one or more subconnections: %s' % str(results)) )

            defs = [ self.getSubConnection(r['provider_nsa'], r['connection_id']) for r in rows ]
            return defer.DeferredList(defs).addCallback(gotSubConns)

        dbconfig = database.Registry.getConfig()
        d = dbconfig.select('sub_connections', where=['service_connection_id = ?', service_connection_key], select='provider_nsa, connection_id')
        d.addCallback(gotResult)
        return d


    @defer.inlineCallbacks
    def reserve(self, header, connection_id, global_reservation_id, description, criteria, request_info=None):

        log.msg('', system=LOG_SYSTEM)
        log.msg('Reserve request from %s' % header.requester_nsa, system=LOG_SYSTEM)
        log.msg('- Path %s -- %s ' % (criteria.service_def.source_stp, criteria.service_def.dest_stp), system=LOG_SYSTEM)
        log.msg('- Trace: %s' % (header.connection_trace), system=LOG_SYSTEM)

        # rethink with modify
        if connection_id != None:
            connection_exists = yield database.ServiceConnection.exists(['connection_id = ?', connection_id])
            if connection_exists:
                raise error.ConnectionExistsError('Connection with id %s already exists' % connection_id)
            raise NotImplementedError('Cannot handly modification of existing connections yet')

        yield self.plugin.connectionRequest(header, connection_id, global_reservation_id, description, criteria)

        if cnt.REQUIRE_TRACE in self.policies:
            if not header.connection_trace:
                log.msg('Rejecting reserve request without connection trace')
                raise error.SecurityError('This NSA (%s) requires a connection trace in the header to create a reservation.' % self.nsa_.urn() )

        if cnt.REQUIRE_USER in self.policies:
            user_attrs  = [ sa for sa in header.security_attributes if sa.type_ == 'user'  ]
            if not user_attrs:
                log.msg('Rejecting reserve request without user security attribute', system=LOG_SYSTEM)
                raise error.SecurityError('This NSA (%s) requires a user attribute in the header to create a reservation.' % self.nsa_.urn() )

        sd = criteria.service_def
        source_stp = sd.source_stp
        dest_stp   = sd.dest_stp

        if not cnt.AGGREGATOR in self.policies:
            # policy check: one endpoint must be in local network
            if not (source_stp.network == self.network or dest_stp.network == self.network):
                raise error.ConnectionCreateError('None of the endpoints terminate in the network, rejecting request (network: %s + %s, nsa network %s)' %
                    (source_stp.network, dest_stp.network, self.network))

        # check that we have path vectors to topologies if we start from here
        if self.network in (source_stp.network, dest_stp.network):
            if source_stp.network != self.network and self.route_vectors.vector(source_stp.network) is None:
                raise error.ConnectionCreateError('No known routes to network %s' % source_stp.network)
            if dest_stp.network != self.network and self.route_vectors.vector(dest_stp.network) is None:
                raise error.ConnectionCreateError('No known routes to network %s' % dest_stp.network)

        # if the link terminates at our network, check that ports exists and that labels match
        if source_stp.network == self.network:
            port = self.network_topology.getPort(source_stp.network + ':' + source_stp.port)
            if port.label() is None:
                if source_stp.label is not None:
                    raise error.ConnectionCreateError('Source STP %s has label specified on port %s without label' % (source_stp, port.name))
            else: # there is a label
                if source_stp.label is None:
                    raise error.ConnectionCreateError('Source STP %s has no label for port %s with label %s' % (source_stp, port.name, port.label().type_))
                if port.label().type_ != source_stp.label.type_:
                    raise error.ConnectionCreateError('Source STP %s label does not match label specified on port %s (%s)' % (source_stp, port.name, port.label().type_))
        if dest_stp.network == self.network:
            port = self.network_topology.getPort(dest_stp.network + ':' + dest_stp.port)
            if port.label() is None:
                if dest_stp.label is not None:
                    raise error.ConnectionCreateError('Destination STP %s has label specified on port %s without label' % (dest_stp, port.name))
            else:
                if port.label().type_ is not None and dest_stp.label is None:
                    raise error.ConnectionCreateError('Destination STP %s has no label for port %s with label %s' % (dest_stp, port.name, port.label().type_))
                if port.label().type_ != dest_stp.label.type_:
                    raise error.ConnectionCreateError('Source STP %s label does not match label specified on port %s (%s)' % (dest_stp, port.name, port.label().type_))


        connection_id = yield self.plugin.createConnectionId()

        conn = database.ServiceConnection(connection_id=connection_id, revision=0, global_reservation_id=global_reservation_id, description=description,
                            requester_nsa=header.requester_nsa, requester_url=header.reply_to, reserve_time=datetime.datetime.utcnow(),
                            reservation_state=state.RESERVE_START, provision_state=state.RELEASED, lifecycle_state=state.CREATED,
                            source_network=source_stp.network, source_port=source_stp.port, source_label=source_stp.label,
                            dest_network=dest_stp.network, dest_port=dest_stp.port, dest_label=dest_stp.label,
                            start_time=criteria.schedule.start_time, end_time=criteria.schedule.end_time,
                            symmetrical=sd.symmetric, directionality=sd.directionality, bandwidth=sd.capacity,
                            security_attributes=header.security_attributes, connection_trace=header.connection_trace)
        yield conn.save()

        # Here we should return / callback and spawn off the path creation

        # Note: At his point STP Labels are candidates and they will need to be changed later

    #    def reserveRequestsDone(results):
    #        successes = [ r[0] for r in results ]
    #        if all(successes):
    #            state.reserved(conn)
    #            log.msg('Connection %s: Reserve succeeded' % self.connection_id, system=LOG_SYSTEM)
    #            self.scheduler.scheduleTransition(self.service_parameters.start_time, scheduled, state.RELEASED)
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
    #            err = self._createAggregateException(results, 'reservations', error.ConnectionCreateError)
    #            raise err

        yield state.reserveChecking(conn) # this also acts a lock

        if conn.source_network == self.network and conn.dest_network == self.network:
            # check for hairpins (unless allowed in policies)
            if not cnt.ALLOW_HAIRPIN in self.policies:
                if conn.source_port == conn.dest_port:
                    raise error.ServiceError('Hairpin connections not allowed.')

            # setup path
            path_info = ( conn.connection_id, self.network, conn.source_port, shortLabel(conn.source_label), conn.dest_port, shortLabel(conn.dest_label) )
            log.msg('Connection %s: Local link creation: %s %s?%s == %s?%s' % path_info, system=LOG_SYSTEM)
            paths = [ [ nsa.Link( nsa.STP(self.network, conn.source_port, conn.source_label),
                                  nsa.STP(self.network, conn.dest_port,   conn.dest_label))  ] ]

            # we should probably specify the connection id to the backend,
            # to make it seem like the aggregator isn't here

        elif self.network in (conn.source_network, conn.dest_network):
            # log about creation and the connection type
            log.msg('Connection %s: Aggregate path creation: %s -> %s' % (conn.connection_id, str(source_stp), str(dest_stp)), system=LOG_SYSTEM)
            # making the connection is the same for all though :-)

            # how to this with path vector
            # 1. find topology to use from vector
            # 2. create abstracted path: local link + rest

            if source_stp.network == self.network:
                local_stp      = source_stp
                remote_stp     = dest_stp
            else:
                local_stp      = dest_stp
                remote_stp     = source_stp

            # we should really find multiple port/link vectors to the remote network, but right now we don't
            vector_port = self.route_vectors.vector(remote_stp.network)
            if vector_port is None:
                raise error.STPResolutionError('No vector to network %s, cannot create circuit' % remote_stp.network)

            log.msg('Vector to %s via port %s' % (remote_stp.network, vector_port), system=LOG_SYSTEM)

            # this really shouldn't fail, so we don't need to check
            demarc_ports = [ self.network_topology.getPort( self.network + ':' + vector_port ) ]

            ldp = demarc_ports[0] # most of the time we will only have one anyway, should iterate and build multiple paths

            local_demarc_port  = ldp.id_.rsplit(':', 1)[1]
            remote_demarc_network, remote_demarc_port = ldp.remote_port.rsplit(':', 1) # [1] # this is wrong in the new naming scheme

            local_link  = nsa.Link( local_stp, nsa.STP(local_stp.network, local_demarc_port, ldp.label()) )
            remote_link = nsa.Link( nsa.STP(remote_demarc_network, remote_demarc_port, ldp.label()), remote_stp) # # the ldp label isn't quite correct

            paths = [ [ local_link, remote_link ] ]
            paths = yield self.plugin.prunePaths(paths)

        elif cnt.AGGREGATOR in self.policies:
            # both endpoints outside the network, proxy aggregation allowed
            log.msg('Connection %s: Remote proxy link creation' % connection_id, system=LOG_SYSTEM)
            paths = [ [ nsa.Link( nsa.STP(conn.source_network, conn.source_port, conn.source_label),
                                  nsa.STP(conn.dest_network,   conn.dest_port,   conn.dest_label))  ] ]
        else:
            # both endpoints outside the network, proxy aggregation not alloweded
            raise error.ConnectionCreateError('None of the endpoints terminate in the network, rejecting request (network: %s + %s, nsa network %s)' %
                (source_stp.network, dest_stp.network, self.network))


        selected_path = paths[0] # shortest path (legacy structure)
        log_path = ' -> '.join( [ str(p) for p in selected_path ] )
        log.msg('Attempting to create path %s' % log_path, system=LOG_SYSTEM)

        for link in selected_path:
            if link.src_stp.network == self.network:
                continue # we got this..
            p = self.provider_registry.getProviderByNetwork(link.src_stp.network)
            if p is None:
                raise error.ConnectionCreateError('No provider for network %s. Cannot create link.' % link.src_stp.network)

        conn_trace = (header.connection_trace or []) + [ self.nsa_.urn() + ':' + conn.connection_id ]
        conn_info = []

        for idx, link in enumerate(selected_path):

            sub_connection_id = None

            if link.src_stp.network == self.network:
                provider_urn = self.nsa_.urn()
                sub_connection_id = connection_id
            else:
                provider_urn = self.provider_registry.getProviderByNetwork(link.src_stp.network)

            c_header = nsa.NSIHeader(self.nsa_.urn(), provider_urn, security_attributes=header.security_attributes, connection_trace=conn_trace)

            sd = nsa.Point2PointService(link.src_stp, link.dst_stp, conn.bandwidth, sd.directionality, sd.symmetric)

            # save info for db saving
            self.reservations[c_header.correlation_id] = {
                                                        'provider_nsa'  : provider_urn,
                                                        'service_connection_id' : conn.id,
                                                        'order_id'       : idx,
                                                        'source_network' : link.src_stp.network,
                                                        'source_port'    : link.src_stp.port,
                                                        'dest_network'   : link.dst_stp.network,
                                                        'dest_port'      : link.dst_stp.port }

            crt = nsa.Criteria(criteria.revision, criteria.schedule, sd)

            provider = self.getProvider(provider_urn)
            # note: request info will only be passed to local backends, remote requester will just ignore it
            d = provider.reserve(c_header, sub_connection_id, conn.global_reservation_id, conn.description, crt, request_info)
            d.addErrback(_logErrorResponse, connection_id, provider_urn, 'reserve')

            conn_info.append( (d, provider_urn) )

            # Don't bother trying to save connection here, wait for reserveConfirmed


        results = yield defer.DeferredList( [ c[0] for c in conn_info ], consumeErrors=True) # doesn't errback
        successes = [ r[0] for r in results ]

        if all(successes):
            log.msg('Connection %s: Reserve acked' % conn.connection_id, system=LOG_SYSTEM)
            defer.returnValue(connection_id)

        else:
            # I think this is out of spec, the aggregator shouldn't do anything here...
            # terminate non-failed connections
            # currently we don't try and be too clever about cleaning, just do it, and switch state
            yield state.terminating(conn)
            defs = []
            reserved_connections = [ (sc_id, provider_urn) for (success,sc_id),(_,provider_urn) in zip(results, conn_info) if success ]
            for (sc_id, provider_urn) in reserved_connections:

                provider = self.getProvider(provider_urn)
                t_header = nsa.NSIHeader(self.nsa_.urn(), provider_urn, security_attributes=header.security_attributes)

                d = provider.terminate(t_header, sc_id)
                d.addCallbacks(
                    lambda c : log.msg('Succesfully terminated sub connection %s at %s after partial reservation failure.' % (sc_id, provider_urn) , system=LOG_SYSTEM),
                    lambda f : log.msg('Error terminating connection after partial-reservation failure: %s' % str(f), system=LOG_SYSTEM)
                )
                defs.append(d)
            dl = defer.DeferredList(defs)
            yield dl
            yield state.terminated(conn)

            # construct provider nsa urns, so we can produce a good error message
            provider_urns = [ ci[1] for ci in conn_info ]
            err = _createAggregateException(connection_id, 'reservations', results, provider_urns, error.ConnectionCreateError)
            raise err


    @defer.inlineCallbacks
    def reserveCommit(self, header, connection_id, request_info=None):

        log.msg('', system=LOG_SYSTEM)
        log.msg('ReserveCommit request. NSA: %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=LOG_SYSTEM)

        conn = yield self.getConnection(connection_id)

        if conn.lifecycle_state == state.TERMINATED:
            raise error.ConnectionGoneError('Connection %s has been terminated' % connection_id)

        yield state.reserveCommit(conn)

        defs = []
        sub_connections = yield self.getSubConnectionsByConnectionKey(conn.id)

        for sc in sub_connections:
            # we assume a provider is available
            provider = self.getProvider(sc.provider_nsa)
            req_header = nsa.NSIHeader(self.nsa_.urn(), sc.provider_nsa, security_attributes=header.security_attributes)
            # we should probably mark as committing before sending message...
            d = provider.reserveCommit(req_header, sc.connection_id, request_info)
            d.addErrback(_logErrorResponse, connection_id, sc.provider_nsa, 'provision')
            defs.append(d)

        results = yield defer.DeferredList(defs, consumeErrors=True)

        successes = [ r[0] for r in results ]
        if all(successes):
            log.msg('Connection %s: ReserveCommit messages acked' % conn.connection_id, system=LOG_SYSTEM)
            defer.returnValue(connection_id)

        else:
            n_success = sum( [ 1 for s in successes if s ] )
            log.msg('Connection %s. Only %i of %i commit acked successfully' % (connection_id, n_success, len(defs)), system=LOG_SYSTEM)
            provider_urns = [ sc.provider_nsa for sc in sub_connections ]
            raise _createAggregateException(connection_id, 'committed', results, provider_urns, error.ConnectionError)


    @defer.inlineCallbacks
    def reserveAbort(self, header, connection_id, request_info=None):

        log.msg('', system=LOG_SYSTEM)
        log.msg('ReserveAbort request. NSA: %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=LOG_SYSTEM)

        conn = yield self.getConnection(connection_id)

        if conn.lifecycle_state == state.TERMINATED:
            raise error.ConnectionGoneError('Connection %s has been terminated' % connection_id)

        yield state.reserveAbort(conn)

        save_defs = []
        defs = []
        sub_connections = yield self.getSubConnectionsByConnectionKey(conn.id)

        for sc in sub_connections:
            save_defs.append( state.reserveAbort(sc) )
            provider = self.getProvider(sc.provider_nsa)
            header = nsa.NSIHeader(self.nsa_.urn(), sc.provider_nsa, security_attributes=header.security_attributes)
            d = provider.reserveAbort(header, sc.connection_id, request_info)
            d.addErrback(_logErrorResponse, connection_id, sc.provider_nsa, 'reserveAbort')
            defs.append(d)

        yield defer.DeferredList(save_defs, consumeErrors=True)

        results = yield defer.DeferredList(defs, consumeErrors=True)

        successes = [ r[0] for r in results ]
        if all(successes):
            log.msg('Connection %s: All ReserveAbort acked' % conn.connection_id, system=LOG_SYSTEM)
            defer.returnValue(connection_id)

        else:
            n_success = sum( [ 1 for s in successes if s ] )
            log.msg('Connection %s. Only %i of %i connections aborted' % (conn.connection_id, len(n_success), len(defs)), system=LOG_SYSTEM)
            provider_urns = [ sc.provider_nsa for sc in sub_connections ]
            raise _createAggregateException(connection_id, 'aborted', results, provider_urns, error.ConnectionError)


    @defer.inlineCallbacks
    def provision(self, header, connection_id, request_info=None):

        log.msg('', system=LOG_SYSTEM)
        log.msg('Provision request. NSA: %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=LOG_SYSTEM)

        conn = yield self.getConnection(connection_id)

        if conn.lifecycle_state == state.TERMINATED:
            raise error.ConnectionGoneError('Connection %s has been terminated' % connection_id)

        yield state.provisioning(conn)

        save_defs = []
        defs = []

        sub_connections = yield self.getSubConnectionsByConnectionKey(conn.id)

        for sc in sub_connections:
            # only bother saving stuff to db if the state is actually changed
            if sc.provision_state != state.PROVISIONING:
                save_defs.append( state.provisioning(sc) )
        if save_defs:
            yield defer.DeferredList(save_defs) #, consumeErrors=True)

        for sc in sub_connections:
            provider = self.getProvider(sc.provider_nsa)
            header = nsa.NSIHeader(self.nsa_.urn(), sc.provider_nsa, security_attributes=header.security_attributes)
            d = provider.provision(header, sc.connection_id, request_info) # request_info will only be passed locally
            d.addErrback(_logErrorResponse, connection_id, sc.provider_nsa, 'provision')
            defs.append(d)

        results = yield defer.DeferredList(defs, consumeErrors=True)
        successes = [ r[0] for r in results ]
        if all(successes):
            # this just means we got an ack from all children
            defer.returnValue(connection_id)
        else:
            n_success = sum( [ 1 for s in successes if s ] )
            log.msg('Connection %s. Provision failure. %i of %i connections successfully acked' % (connection_id, n_success, len(defs)), system=LOG_SYSTEM)
            provider_urns = [ sc.provider_nsa for sc in sub_connections ]
            raise _createAggregateException(connection_id, 'provision', results, provider_urns, error.ConnectionError)


    @defer.inlineCallbacks
    def release(self, header, connection_id, request_info=None):

        log.msg('', system=LOG_SYSTEM)
        log.msg('Release request. NSA: %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=LOG_SYSTEM)

        conn = yield self.getConnection(connection_id)

        if conn.lifecycle_state == state.TERMINATED:
            raise error.ConnectionGoneError('Connection %s has been terminated' % connection_id)

        yield state.releasing(conn)

        save_defs = []
        defs = []

        sub_connections = yield self.getSubConnectionsByConnectionKey(conn.id)

        for sc in sub_connections:
            save_defs.append( state.releasing(sc) )
        yield defer.DeferredList(save_defs) #, consumeErrors=True)

        for sc in sub_connections:
            provider = self.getProvider(sc.provider_nsa)
            header = nsa.NSIHeader(self.nsa_.urn(), sc.provider_nsa, security_attributes=header.security_attributes)
            d = provider.release(header, sc.connection_id, request_info)
            d.addErrback(_logErrorResponse, connection_id, sc.provider_nsa, 'release')
            defs.append(d)

        yield defer.DeferredList(save_defs, consumeErrors=True)

        results = yield defer.DeferredList(defs, consumeErrors=True)
        successes = [ r[0] for r in results ]
        if all(successes):
            # got ack from all children
            defer.returnValue(connection_id)

        else:
            n_success = sum( [ 1 for s in successes if s ] )
            log.msg('Connection %s. Only %i of %i connections successfully released' % (conn.connection_id, n_success, len(defs)), system=LOG_SYSTEM)
            provider_urns = [ sc.provider_nsa for sc in sub_connections ]
            raise _createAggregateException(connection_id, 'release', results, provider_urns, error.ConnectionError)


    @defer.inlineCallbacks
    def terminate(self, header, connection_id, request_info=None):

        log.msg('', system=LOG_SYSTEM)
        log.msg('Terminate request. NSA: %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=LOG_SYSTEM)

        conn = yield self.getConnection(connection_id)

        if conn.lifecycle_state == state.TERMINATED:
            defer.returnValue(connection_id) # all good

        yield state.terminating(conn)

        defs = []
        sub_connections = yield self.getSubConnectionsByConnectionKey(conn.id)

        for sc in sub_connections:
            # we assume a provider is available
            provider = self.getProvider(sc.provider_nsa)
            header = nsa.NSIHeader(self.nsa_.urn(), sc.provider_nsa, security_attributes=header.security_attributes)
            d = provider.terminate(header, sc.connection_id, request_info)
            d.addErrback(_logErrorResponse, connection_id, sc.provider_nsa, 'terminate')
            defs.append(d)

        results = yield defer.DeferredList(defs, consumeErrors=True)

        successes = [ r[0] for r in results ]
        if all(successes):
            log.msg('Connection %s: All sub connections(%i) acked terminated' % (conn.connection_id, len(defs)), system=LOG_SYSTEM)
            defer.returnValue(connection_id)
        else:
            # we are now in an inconsistent state...
            n_success = sum( [ 1 for s in successes if s ] )
            log.msg('Connection %s. Only %i of %i connections successfully terminated' % (conn.connection_id, n_success, len(defs)), system=LOG_SYSTEM)
            provider_urns = [ sc.provider_nsa for sc in sub_connections ]
            raise _createAggregateException(connection_id, 'terminate', results, provider_urns, error.ConnectionError)



    @defer.inlineCallbacks
    def querySummary(self, header, connection_ids=None, global_reservation_ids=None, request_info=None):

        log.msg('QuerySummary request from %s. CID: %s. GID: %s' % (header.requester_nsa, connection_ids, global_reservation_ids), system=LOG_SYSTEM)

        try:
            if connection_ids:
                conns = yield database.ServiceConnection.find(where=['requester_nsa = ? AND connection_id IN ?', header.requester_nsa, tuple(connection_ids) ] )
            elif global_reservation_ids:
                conns = yield database.ServiceConnection.find(where=['requester_nsa = ? AND global_reservation_ids IN ?', header.requester_nsa, tuple(global_reservation_ids) ] )
            else:
                conns = yield database.ServiceConnection.find(where=['requester_nsa = ?', header.requester_nsa ] )

            # largely copied from genericbackend, merge later
            reservations = []
            for c in conns:

                source_stp  = nsa.STP(c.source_network, c.source_port, c.source_label)
                dest_stp    = nsa.STP(c.dest_network, c.dest_port, c.dest_label)
                schedule    = nsa.Schedule(c.start_time, c.end_time)
                sd          = nsa.Point2PointService(source_stp, dest_stp, c.bandwidth, cnt.BIDIRECTIONAL, False, None)
                criteria    = nsa.QueryCriteria(c.revision, schedule, sd)

                sub_conns = yield self.getSubConnectionsByConnectionKey(c.id)
                if len(sub_conns) == 0: # apparently this can happen
                    data_plane_status = (False, 0, False)
                else:
                    aggr_active     = all( [ sc.data_plane_active     for sc in sub_conns ] )
                    aggr_version    = max( [ sc.data_plane_version    for sc in sub_conns ] ) or 0 # can be None otherwise
                    aggr_consistent = all( [ sc.data_plane_consistent for sc in sub_conns ] )
                    data_plane_status = (aggr_active, aggr_version, aggr_consistent)

                states = (c.reservation_state, c.provision_state, c.lifecycle_state, data_plane_status)
                notification_id = self.getNotificationId()
                result_id = 0

                ci = nsa.ConnectionInfo(c.connection_id, c.global_reservation_id, c.description, cnt.EVTS_AGOLE, [ criteria ],
                                        self.nsa_.urn(), c.requester_nsa, states, notification_id, result_id)
                reservations.append(ci)

            self.parent_requester.querySummaryConfirmed(header, reservations)

        except Exception as e:
            log.msg('Error during querySummary request: %s' % str(e), system=LOG_SYSTEM)
            raise e


    @defer.inlineCallbacks
    def queryRecursive(self, header, connection_ids, global_reservation_ids, request_info=None):

        log.msg('QueryRecursive request from %s. CID: %s. GID: %s' % (header.requester_nsa, connection_ids, global_reservation_ids), system=LOG_SYSTEM)

        # the semantics for global reservation id and query recursive is extremely wonky, so we don't do it
        if global_reservation_ids:
            raise error.UnsupportedParameter("Global Reservation Id not supported in queryRecursive (has wonky-monkey-on-acid semantics, don't use it)")

        # recursive queries for all connections is a bad idea, say no to that
        if not connection_ids:
            raise error.MissingParameterError("At least one connection id must be specified, refusing to do recursive query for all connections")

        # because segmenting the requests is a PITA
        if len(connection_ids) > 1:
            raise error.UnsupportedParameter("Can only perform queryRecursive for a single connection id.")

        try:
            conn = yield self.getConnection(connection_ids[0])

            sub_connections = yield self.getSubConnectionsByConnectionKey(conn.id)

            cb_header = nsa.NSIHeader(header.requester_nsa, self.nsa_.urn(), header.correlation_id, reply_to=header.reply_to, security_attributes=header.security_attributes)
            self.query_requests[cb_header.correlation_id]  = (cb_header, conn, len(sub_connections) )

            defs = []
            for sc in sub_connections:
                provider = self.getProvider(sc.provider_nsa)
                sch = nsa.NSIHeader(self.nsa_.urn(), sc.provider_nsa, security_attributes=header.security_attributes)
                d = provider.queryRecursive(sch, [ sc.connection_id ] , None, request_info)
                d.addErrback(_logErrorResponse, 'queryRecursive', sc.provider_nsa, 'queryRecursive')
                defs.append(d)

                self.query_calls[sch.correlation_id] = (cb_header.correlation_id, None)

            results = yield defer.DeferredList(defs, consumeErrors=True)
            successes = [ r[0] for r in results ]
            if all(successes):
                # this just means we got an ack from all children
                defer.returnValue(None)

            else:
                n_success = sum( [ 1 for s in successes if s ] )
                log.msg('QueryRecursive failure. %i of %i connections successfully replied' % (n_success, len(defs)), system=LOG_SYSTEM)
                # we should really clear out the temporary state here...
                provider_urns = [ sc.provider_nsa for sc in sub_connections ]
                raise _createAggregateException('', 'queryRecursive', results, provider_urns, error.ConnectionError)

        except ValueError as e:
            log.msg('Error during queryRecursive request: %s' % str(e), system=LOG_SYSTEM)
            raise e


    @defer.inlineCallbacks
    def queryRecursiveConfirmed(self, header, sub_result):

        @defer.inlineCallbacks
        def createCQR(conn, children=None):
            # can we make this generic?
            c = conn

            source_stp = nsa.STP(c.source_network, c.source_port, c.source_label)
            dest_stp = nsa.STP(c.dest_network, c.dest_port, c.dest_label)

            schedule = nsa.Schedule(c.start_time, c.end_time)
            sd = nsa.Point2PointService(source_stp, dest_stp, c.bandwidth, cnt.BIDIRECTIONAL, False, None, None)

            criteria = nsa.QueryCriteria(c.revision, schedule, sd, children)

            sub_conns = yield self.getSubConnectionsByConnectionKey(c.id)
            if len(sub_conns) == 0: # apparently this can happen
                data_plane_status = (False, 0, False)
            else:
                aggr_active     = all( [ sc.data_plane_active     for sc in sub_conns ] )
                aggr_version    = max( [ sc.data_plane_version    for sc in sub_conns ] ) or 0 # can be None otherwise
                aggr_consistent = all( [ sc.data_plane_consistent for sc in sub_conns ] )
                data_plane_status = (aggr_active, aggr_version, aggr_consistent)

            states = (c.reservation_state, c.provision_state, c.lifecycle_state, data_plane_status)
            notification_id = self.getNotificationId()
            result_id = notification_id

            ci = nsa.ConnectionInfo(c.connection_id, c.global_reservation_id, c.description, cnt.EVTS_AGOLE, [ criteria ],
                                    self.nsa_.urn(), c.requester_nsa, states, notification_id, result_id)
            defer.returnValue(ci)

        # ---

        log.msg('queryRecursiveConfirmed from %s.' % (header.provider_nsa,), system=LOG_SYSTEM)

        if not header.correlation_id in self.query_calls:
            log.msg('queryRecursiveConfirmed could not match correlation id %s' % header.correlation_id, system=LOG_SYSTEM)
            return

        cbh_correlation_id, res = self.query_calls[header.correlation_id]
        if res:
            log.msg('queryRecursiveConfirmed : Already have result for correlation id %s' % header.correlation_id, system=LOG_SYSTEM)
            return

        # update temporary result structure

        self.query_calls[header.correlation_id] = cbh_correlation_id, sub_result

        # done updating

        # check if all sub results have been received
        cb_header, conn, count = self.query_requests[cbh_correlation_id]
        scr = [ res[0] for cbhci, res in self.query_calls.values() if res and cbhci == cbh_correlation_id ]

        if len(scr) == count:
            # all results back, can emit

            # clear temporary structure
            self.query_requests.pop(cbh_correlation_id)
            for k,v in list(self.query_calls.items()): # make a copy to avoid changing the dict while iterating
                cbhci, res = v
                if cbhci == cbh_correlation_id:
                    self.query_calls.pop(k)

            log.msg('QueryRecursive : Emitting to parent requester', system=LOG_SYSTEM)
            results = yield createCQR(conn, scr)
            self.parent_requester.queryRecursiveConfirmed(cb_header, [ results ] )

        else:
            log.msg('QueryRecursive : Still neeed %i/%i results to emit result' % (count-len(scr), count), system=LOG_SYSTEM)


    def queryNotification(self, header, connection_id, start_notification, end_notification):

        log.msg('QueryNotification request from %s. CID: %s. %s-%s' % (header.requester_nsa, connection_id, start_notification, end_notification), system=LOG_SYSTEM)
        raise NotImplementedError('queryNotification not yet implemented in aggregator')

    # --
    # Requester API
    # --

    @defer.inlineCallbacks
    def reserveConfirmed(self, header, connection_id, global_reservation_id, description, criteria):

        log.msg('', system=LOG_SYSTEM)
        log.msg('reserveConfirm from %s. Connection ID: %s' % (header.provider_nsa, connection_id), system=LOG_SYSTEM)

        if not header.correlation_id in self.reservations:
            msg = 'Unrecognized correlation id %s in reserveConfirmed. Connection ID %s. NSA %s' % (header.correlation_id, connection_id, header.provider_nsa)
            log.msg(msg, system=LOG_SYSTEM)
            raise error.ConnectionNonExistentError(msg)

        org_provider_nsa = self.reservations[header.correlation_id]['provider_nsa']
        if header.provider_nsa != org_provider_nsa:
            log.msg('Provider NSA in header %s for reserveConfirmed does not match saved identity %s' % (header.provider_nsa, org_provider_nsa), system=LOG_SYSTEM)
            raise error.SecurityError('Provider NSA for connection does not match saved identity')

        resv_info = self.reservations.pop(header.correlation_id)

        # gid and desc should be identical, not checking, same with bandwidth, schedule, etc

        sd = criteria.service_def
        # check that path matches our intent
        if sd.source_stp.network != resv_info['source_network']:
            log.msg('reserveConfirmed: source network mismatch (%s != %s)' % (resv_info['source_network'], sd.source_stp.network), system=LOG_SYSTEM)
        if sd.source_stp.port    != resv_info['source_port']:
            log.msg('reserveConfirmed: source port mismatch (%s != %s' % (resv_info['source_port'], sd.source_stp.port), system=LOG_SYSTEM)
        if sd.dest_stp.network   != resv_info['dest_network']:
            log.msg('reserveConfirmed: dest network mismatch', system=LOG_SYSTEM)
        if sd.dest_stp.port      != resv_info['dest_port']:
            log.msg('reserveConfirmed: dest port mismatch', system=LOG_SYSTEM)
        if not (sd.source_stp.label is None or sd.source_stp.label.singleValue()):
            log.msg('reserveConfirmed: source label is no a single value', system=LOG_SYSTEM)
        if not (sd.dest_stp.label is None or sd.dest_stp.label.singleValue()):
            log.msg('reserveConfirmed: dest label is no a single value', system=LOG_SYSTEM)

        # skip label check for now
        #sd.source_stp.label.intersect(sub_connection.source_label)
        #sd.dest_stp.label.intersect(sub_connection.dest_label)

        db_start_time = criteria.schedule.start_time.isoformat() if criteria.schedule.start_time is not None else None
        db_end_time = criteria.schedule.end_time.isoformat()     if criteria.schedule.end_time   is not None else None

        # save sub connection in database
        sc = database.SubConnection(provider_nsa=org_provider_nsa, connection_id=connection_id, local_link=False, # remove local link sometime
                                    revision=criteria.revision, service_connection_id=resv_info['service_connection_id'], order_id=resv_info['order_id'],
                                    global_reservation_id=global_reservation_id, description=description,
                                    reservation_state=state.RESERVE_HELD, provision_state=state.RELEASED, lifecycle_state=state.CREATED, data_plane_active=False,
                                    source_network=sd.source_stp.network, source_port=sd.source_stp.port, source_label=sd.source_stp.label,
                                    dest_network=sd.dest_stp.network, dest_port=sd.dest_stp.port, dest_label=sd.dest_stp.label,
                                    start_time=db_start_time, end_time=db_end_time, bandwidth=sd.capacity)

        yield sc.save()

        # figure out if we can aggregate upwards

        conn = yield self.getConnectionByKey(sc.service_connection_id)
        sub_conns = yield self.getSubConnectionsByConnectionKey(conn.id)

        if sc.order_id == 0:
            conn.source_label = sd.source_stp.label
        if sc.order_id == len(sub_conns)-1:
            conn.dest_label = sd.dest_stp.label

        yield conn.save()

        outstanding_calls = [ v for v in self.reservations.values() if v.get('service_connection_id') == resv_info['service_connection_id'] ]
        if len(outstanding_calls) > 0:
            log.msg('Connection %s: Still missing %i reserveConfirmed call(s) to aggregate' % (conn.connection_id, len(outstanding_calls)), system=LOG_SYSTEM)
            return

        # if we get responses very close, multiple requests can trigger this, so we check main state as well
        if all( [ sc.reservation_state == state.RESERVE_HELD for sc in sub_conns ] ) and conn.reservation_state != state.RESERVE_HELD:
            log.msg('Connection %s: All sub connections reserve held, can emit reserveConfirmed' % (conn.connection_id), system=LOG_SYSTEM)
            yield state.reserveHeld(conn)
            header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn())
            source_stp = nsa.STP(conn.source_network, conn.source_port, conn.source_label)
            dest_stp   = nsa.STP(conn.dest_network,   conn.dest_port,   conn.dest_label)
            schedule = nsa.Schedule(conn.start_time, conn.end_time)
            sd = nsa.Point2PointService(source_stp, dest_stp, conn.bandwidth, cnt.BIDIRECTIONAL, False, None) # we fake some thing that is not yet in the db
            conn_criteria = nsa.Criteria(conn.revision, schedule, sd)
            # This is just oneshot, we don't really care if it fails, as we cannot do anything about it
            self.parent_requester.reserveConfirmed(header, conn.connection_id, conn.global_reservation_id, conn.description, conn_criteria)

        else:
            log.msg('Connection %s: Still missing reserveConfirmed messages before emitting to parent' % (conn.connection_id), system=LOG_SYSTEM)


    @defer.inlineCallbacks
    def reserveFailed(self, header, connection_id, connection_states, err):

        log.msg('', system=LOG_SYSTEM)
        log.msg('reserveFailed from %s. Connection ID: %s. Error: %s' % (header.provider_nsa, connection_id, err), system=LOG_SYSTEM)

        if not header.correlation_id in self.reservations:
            msg = 'Unrecognized correlation id %s in reserveFailed. Connection ID %s. NSA %s' % (header.correlation_id, connection_id, header.provider_nsa)
            log.msg(msg, system=LOG_SYSTEM)
            raise error.ConnectionNonExistentError(msg)

        org_provider_nsa = self.reservations[header.correlation_id]['provider_nsa']
        if header.provider_nsa != org_provider_nsa:
            log.msg('Provider NSA in header %s for reserveFailed does not match saved identity %s' % (header.provider_nsa, org_provider_nsa), system=LOG_SYSTEM)
            raise error.SecurityError('Provider NSA for connection does not match saved identity')

        resv_info = self.reservations.pop(header.correlation_id)

        service_connection_key = resv_info['service_connection_id']

        conn = yield self.getConnectionByKey(service_connection_key)
        if conn.reservation_state != state.RESERVE_FAILED: # since we can fail multiple times
            yield state.reserveFailed(conn)

        header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn())
        self.parent_requester.reserveFailed(header, conn.connection_id, connection_states, err)


    @defer.inlineCallbacks
    def reserveCommitConfirmed(self, header, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('ReserveCommit Confirmed for sub connection %s. NSA %s ' % (connection_id, header.provider_nsa), system=LOG_SYSTEM)

        sub_connection = yield self.getSubConnection(header.provider_nsa, connection_id)
        sub_connection.reservation_state = state.RESERVE_START
        yield sub_connection.save()

        conn = yield self.getConnectionByKey(sub_connection.service_connection_id)
        sub_conns = yield self.getSubConnectionsByConnectionKey(conn.id)

        # if we get responses very close, multiple requests can trigger this, so we check main state as well
        if all( [ sc.reservation_state == state.RESERVE_START for sc in sub_conns ] ) and conn.reservation_state != state.RESERVE_START:
            yield state.reserved(conn)
            header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn())
            self.parent_requester.reserveCommitConfirmed(header, conn.connection_id)
            self.plugin.connectionCreated(conn)


    @defer.inlineCallbacks
    def reserveAbortConfirmed(self, header, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('ReserveAbort confirmed for sub connection %s. NSA %s ' % (connection_id, header.provider_nsa), system=LOG_SYSTEM)

        sub_connection = yield self.getSubConnection(header.provider_nsa, connection_id)
        sub_connection.reservation_state = state.RESERVE_START
        yield sub_connection.save()

        conn = yield self.getConnectionByKey(sub_connection.service_connection_id)
        sub_conns = yield self.getSubConnectionsByConnectionKey(conn.id)

        # if we get responses very close, multiple requests can trigger this, so we check main state as well
        if all( [ sc.reservation_state == state.RESERVE_START for sc in sub_conns ] ) and conn.reservation_state != state.RESERVE_START:
            yield state.reserved(conn)
            header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn())
            self.parent_requester.reserveAbortConfirmed(header, conn.connection_id)


    @defer.inlineCallbacks
    def provisionConfirmed(self, header, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('Provision Confirmed for sub connection %s. NSA %s ' % (connection_id, header.provider_nsa), system=LOG_SYSTEM)

        sub_connection = yield self.getSubConnection(header.provider_nsa, connection_id)
        yield state.provisioned(sub_connection)

        conn = yield self.getConnectionByKey(sub_connection.service_connection_id)
        sub_conns = yield self.getSubConnectionsByConnectionKey(conn.id)

        # if we get responses very close, multiple requests can trigger this, so we check main state as well
        if all( [ sc.provision_state == state.PROVISIONED for sc in sub_conns ] ) and conn.provision_state != state.PROVISIONED:
            yield state.provisioned(conn)
            req_header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn())
            self.parent_requester.provisionConfirmed(req_header, conn.connection_id)


    @defer.inlineCallbacks
    def releaseConfirmed(self, header, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('Release confirmed for sub connection %s. NSA %s ' % (connection_id, header.provider_nsa), system=LOG_SYSTEM)

        sub_connection = yield self.getSubConnection(header.provider_nsa, connection_id)
        yield state.released(sub_connection)

        conn = yield self.getConnectionByKey(sub_connection.service_connection_id)
        sub_conns = yield self.getSubConnectionsByConnectionKey(conn.id)

        # if we get responses very close, multiple requests can trigger this, so we check main state as well
        if all( [ sc.provision_state == state.RELEASED for sc in sub_conns ] ) and conn.provision_state != state.RELEASED:
            yield state.released(conn)
            req_header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn())
            self.parent_requester.releaseConfirmed(req_header, conn.connection_id)


    @defer.inlineCallbacks
    def terminateConfirmed(self, header, connection_id):

        sub_connection = yield self.getSubConnection(header.provider_nsa, connection_id)
        sub_connection.lifecycle_state = state.TERMINATED
        yield sub_connection.save()

        conn = yield self.getConnectionByKey(sub_connection.service_connection_id)
        sub_conns = yield self.getSubConnectionsByConnectionKey(conn.id)

        # if we get responses very close, multiple requests can trigger this, so we check main state as well
        if all( [ sc.lifecycle_state == state.TERMINATED for sc in sub_conns ] ) and conn.lifecycle_state != state.TERMINATED:
            yield state.terminated(conn)
            header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn())
            self.parent_requester.terminateConfirmed(header, conn.connection_id)
            self.plugin.connectionTerminated(conn)

    # --


    def doTimeout(self, conn, timeout_value, org_connection_id, org_nsa):
        header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn(), reply_to=conn.requester_url)
        now = datetime.datetime.utcnow()
        self.parent_requester.reserveTimeout(header, conn.connection_id, 0, now, timeout_value, org_connection_id, org_nsa)


    def doErrorEvent(self, conn, notification_id, event, info, service_ex=None):
        header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn(), reply_to=conn.requester_url)
        now = datetime.datetime.utcnow()
        self.parent_requester.errorEvent(header, conn.connection_id, notification_id, now, event, info, service_ex)

    # --

    @defer.inlineCallbacks
    def reserveTimeout(self, header, connection_id, notification_id, timestamp, timeout_value, org_connection_id, org_nsa):

        log.msg("reserveTimeout from %s:%s" % (header.provider_nsa, connection_id), system=LOG_SYSTEM)

        sub_conn = yield self.getSubConnection(header.provider_nsa, connection_id)

        yield state.reserveTimeout(sub_conn)

        conn = yield self.getConnectionByKey(sub_conn.service_connection_id)
        sub_conns = yield self.getSubConnectionsByConnectionKey(conn.id)

        if conn.reservation_state == state.RESERVE_FAILED:
            log.msg("Connection %s: reserveTimeout: Connection has already failed, not notifying parent" % conn.connection_id, system=LOG_SYSTEM)
        elif sum ( [ 1 if sc.reservation_state == state.RESERVE_TIMEOUT else 0 for sc in sub_conns ] ) == 1:
            log.msg("Connection %s: reserveTimeout, first occurance, notifying parent" % conn.connection_id, system=LOG_SYSTEM)
            header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn(), reply_to=conn.requester_url)
            self.parent_requester.reserveTimeout(header, conn.connection_id, notification_id, timestamp, timeout_value, org_connection_id, org_nsa)
        else:
            log.msg("Connection %s: reserveTimeout: Second or later reserveTimeout, not notifying parent" % conn.connection_id, system=LOG_SYSTEM)


    @defer.inlineCallbacks
    def dataPlaneStateChange(self, header, connection_id, notification_id, timestamp, dps):

        active, version, consistent = dps
        log.msg("Data plane change for sub connection: %s Active: %s, version %i, consistent: %s" % \
                 (connection_id, active, version, consistent), system=LOG_SYSTEM)

        sub_conn = yield self.getSubConnection(header.provider_nsa, connection_id)

        sub_conn.data_plane_active      = active
        sub_conn.data_plane_version     = version
        sub_conn.data_plane_consistent  = consistent

        yield sub_conn.save()

        conn = yield self.getConnectionByKey(sub_conn.service_connection_id)
        sub_conns = yield self.getSubConnectionsByConnectionKey(conn.id)

        # At some point we should check if data plane aggregated state actually changes and only emit for those that change

        # do notification
        actives  = [ sc.data_plane_active     for sc in sub_conns ]
        aggr_active     = all( actives )
        aggr_version    = max( [ sc.data_plane_version    for sc in sub_conns ] )
        aggr_consistent = all( [ sc.data_plane_consistent for sc in sub_conns ] ) and all( [ a == actives[0] for a in actives ] ) # we need version here

        header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn(), reply_to=conn.requester_url)
        now = datetime.datetime.utcnow()
        data_plane_status = (aggr_active, aggr_version, aggr_consistent)

        log.msg("Connection %s: Aggregated data plane status: Active %s, version %s, consistent %s" % \
            (conn.connection_id, aggr_active, aggr_version, aggr_consistent), system=LOG_SYSTEM)

        self.parent_requester.dataPlaneStateChange(header, conn.connection_id, 0, now, data_plane_status)

    #@defer.inlineCallbacks
    def error(self, header, nsa_id, connection_id, service_type, error_id, text, variables, child_ex):

        log.msg("errorEvent: Connection %s from %s: %s, %s" % (connection_id, nsa_id, text, str(variables)), system=LOG_SYSTEM)

        if header.provider_nsa != nsa_id:
            log.msg("errorEvent: NSA Id for error is different from provider (provider: %s, nsa: %s, cannot handle error, due to protocol design issue." % \
                    (header.provider_nsa, nsa_id), system=LOG_SYSTEM)
            return
            #defer.returnValue(None)

        # do we need to do anything here?
        #sub_conn = yield self.getSubConnection(header.provider_nsa, connection_id)
        #conn = yield self.getConnectionByKey(sub_conn.service_connection_id)

        # this is wrong....
        self.parent_requester.error(header, nsa_id, connection_id, service_type, error_id, text, variables, None)


    @defer.inlineCallbacks
    def errorEvent(self, header, connection_id, notification_id, timestamp, event, info, service_ex):

        # should mark sub connection as terminated / failed
        sub_conn = yield self.getSubConnection(header.provider_nsa, connection_id)

        conn = yield self.getConnectionByKey(sub_conn.service_connection_id)
        sub_conns = yield self.getSubConnectionsByConnectionKey(conn.id)

        if len(sub_conns) == 1:
            log.msg("errorEvent: One sub connection for connection %s, notifying" % conn.connection_id, system=LOG_SYSTEM)
            self.doErrorEvent(conn, notification_id, event, info, service_ex)
        else:
            raise NotImplementedError('Cannot handle errorEvent for connection with more than one sub connection')


    def querySummaryConfirmed(self, header, summary_results):
        raise NotImplementedError('querySummaryConfirmed is not yet implemented in aggregater')


    def queryNotificationFailed(self, header, service_exception):
        raise NotImplementedError('queryNotificationFailed is not yet implemented in aggregater')

