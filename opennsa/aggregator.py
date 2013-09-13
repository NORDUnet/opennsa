"""
Connection abstraction.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""
import string
import random
import datetime

from zope.interface import implements

from twisted.python import log, failure
from twisted.internet import defer

from opennsa.interface import INSIProvider, INSIRequester
from opennsa import error, nsa, state, database



LOG_SYSTEM = 'Aggregator'



#def connPath(conn):
#    """
#    Utility function for getting a string with the source and dest STP of connection.
#    """
#    source_stp, dest_stp = conn.stps()
#    return '<%s:%s--%s:%s>' % (source_stp.network, source_stp.endpoint, dest_stp.network, dest_stp.endpoint)


def shortLabel(labels):
    # create a log friendly string representation of a lbel
    lbs = []
    for label in labels:
        if '}' in label.type_:
            name = label.type_.split('}',1)[1]
        else:
            name = label.type_
        lbs.append( name + ':' + label.labelValue() )
    return ','.join(lbs)


def _buildErrorMessage(results, action):

    # should probably seperate loggin somehow
    failures = [ fail for (success, fail) in results if success is False ]
    for f in failures:
        print f
    failure_msgs = [ f.getErrorMessage() for f in failures ]

    log.msg('Connection ... %i failures' % len(failures), system=LOG_SYSTEM)
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

    err = _createAggregateException(results, action)
    return failure.Failure(err)



class Aggregator:

    implements(INSIProvider, INSIRequester)

    def __init__(self, network, nsa_, topology, parent_requester, provider_registry):
        self.network = network
        self.nsa_ = nsa_
        self.topology = topology

        self.parent_requester   = parent_requester
        self.provider_registry  = provider_registry

        self.reservations       = {} # correlation_id -> info
        self.notification_id    = 0


    def getNotificationId(self):
        nid = self.notification_id
        self.notification_id += 1
        return nid


    def getProvider(self, nsi_agent_urn):
        return self.provider_registry.getProvider(nsi_agent_urn)


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


    def getSubConnection(self, provider_nsa, connection_id):

        def gotResult(connections):
            # we should get 0 or 1 here since provider_nsa + connection id is unique
            if len(connections) == 0:
                return defer.fail( error.ConnectionNonExistentError('No sub connection with connection id %s at provider %s' % (connection_id, provider_nsa) ) )
            return connections[0]

        d = database.SubConnection.findBy(provider_nsa=provider_nsa, connection_id=connection_id)
        d.addCallback(gotResult)
        return d


    @defer.inlineCallbacks
    def reserve(self, header, connection_id, global_reservation_id, description, service_params):

        log.msg('', system=LOG_SYSTEM)
        log.msg('Reserve request. NSA: %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=LOG_SYSTEM)

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

        conn = database.ServiceConnection(connection_id=connection_id, revision=0, global_reservation_id=global_reservation_id, description=description,
                            requester_nsa=header.requester_nsa, requester_url=header.reply_to, reserve_time=datetime.datetime.utcnow(),
                            reservation_state=state.RESERVE_START, provision_state=state.RELEASED, lifecycle_state=state.CREATED,
                            source_network=source_stp.network, source_port=source_stp.port, source_labels=source_stp.labels,
                            dest_network=dest_stp.network, dest_port=dest_stp.port, dest_labels=dest_stp.labels,
                            start_time=service_params.start_time, end_time=service_params.end_time, bandwidth=service_params.bandwidth)
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
    #            err = self._createAggregateFailure(results, 'reservations', error.ConnectionCreateError)
    #            return err

        yield state.reserveChecking(conn) # this also acts a lock

        if conn.source_network == self.network and conn.dest_network == self.network:
            path_info = ( conn.connection_id, self.network, conn.source_port, shortLabel(conn.source_labels), conn.dest_port, shortLabel(conn.dest_labels) )
            log.msg('Connection %s: Local link creation: %s %s#%s -> %s#%s' % path_info, system=LOG_SYSTEM)
            paths = [ [ nsa.Link(self.network, conn.source_port, conn.dest_port, conn.source_labels, conn.dest_labels) ] ]

        else:
            # log about creation and the connection type
            path_info = ( conn.connection_id, conn.source_network, conn.source_port, conn.dest_network, conn.dest_port, conn.requester_nsa)
            log.msg('Connection %s: Aggregate path creation: %s:%s -> %s:%s (%s)' % path_info, system=LOG_SYSTEM)
            # making the connection is the same for all though :-)
            paths = self.topology.findPaths(source_stp, dest_stp, conn.bandwidth)

            # error out if we could not find a path
            if not paths:
                error_msg = 'Could not find a path for route %s:%s -> %s:%s' % (source_stp.network, source_stp.port, dest_stp.network, dest_stp.port)
                log.msg(error_msg, system=LOG_SYSTEM)
                raise error.TopologyError(error_msg)

            paths.sort(key=lambda e : len(e))

        selected_path = paths[0] # shortest path
        log_path = ' -> '.join( [ str(p) for p in selected_path ] )
        log.msg('Attempting to create path %s' % log_path, system=LOG_SYSTEM)

        for link in selected_path:
            try:
                self.topology.getNSA(link.network)
            except error.TopologyError:
                raise error.ConnectionCreateError('No provider for network %s. Cannot create link' % link.network)

        conn_info = []
        for idx, link in enumerate(selected_path):

            provider_nsa = self.topology.getNSA(link.network)
            provider     = self.getProvider(provider_nsa.urn())

            header = nsa.NSIHeader(self.nsa_.urn(), provider_nsa.urn(), [])

            ssp  = nsa.ServiceParameters(conn.start_time, conn.end_time,
                                         nsa.STP(link.network, link.src_port, labels=link.src_labels),
                                         nsa.STP(link.network, link.dst_port, labels=link.dst_labels),
                                         conn.bandwidth)

            # save info for db saving
            self.reservations[header.correlation_id] = {
                                                        'provider_nsa'  : provider_nsa.urn(),
                                                        'service_connection_id' : conn.id,
                                                        'order_id'       : idx,
                                                        'source_network' : link.network,
                                                        'source_port'    : link.src_port,
                                                        'dest_network'   : link.network,
                                                        'dest_port'      : link.dst_port }

            d = provider.reserve(header, None, conn.global_reservation_id, conn.description, ssp)
            conn_info.append( (d, provider_nsa) )

            # Don't bother trying to save connection here, wait for reserveConfirmed

#            @defer.inlineCallbacks
#            def reserveResponse(connection_id, link_provider_nsa, order_id):
#                # need to collapse the label values when getting reserveConfirm
#                log.msg('Connection reservation for %s via %s acked' % (connection_id, link_provider_nsa), debug=True, system=LOG_SYSTEM)
#                # should probably do some sanity checks here
#                sp = service_params
#                local_link = True if link_provider_nsa == self.nsa_ else False
#                sc = database.SubConnection(provider_nsa=link_provider_nsa.urn(),
#                                            connection_id=connection_id, local_link=local_link, revision=0, service_connection_id=conn.id, order_id=order_id,
#                                            global_reservation_id=global_reservation_id, description=description,
#                                            reservation_state=state.RESERVE_START, provision_state=state.RELEASED, lifecycle_state=state.CREATED, data_plane_active=False,
#                                            source_network=sp.source_stp.network, source_port=sp.source_stp.port, source_labels=sp.source_stp.labels,
#                                            dest_network=sp.dest_stp.network, dest_port=sp.dest_stp.port, dest_labels=sp.dest_stp.labels,
#                                            start_time=sp.start_time.isoformat(), end_time=sp.end_time.isoformat(), bandwidth=sp.bandwidth)
#                yield sc.save()
#                defer.returnValue(sc)
#
#            d.addCallback(reserveResponse, provider_nsa, idx)

        results = yield defer.DeferredList( [ c[0] for c in conn_info ], consumeErrors=True) # doesn't errback
        successes = [ r[0] for r in results ]

        if all(successes):
            log.msg('Connection %s: Reserve acked' % conn.connection_id, system=LOG_SYSTEM)
            defer.returnValue(connection_id)

        else:
            # terminate non-failed connections
            # currently we don't try and be too clever about cleaning, just do it, and switch state
            yield state.terminating(conn)
            defs = []
            reserved_connections = [ (sc_id, provider_nsa) for (success,sc_id),(_,provider_nsa) in zip(results, conn_info) if success ]
            for (sc_id, provider_nsa) in reserved_connections:

                provider = self.getProvider(provider_nsa.urn())
                header = nsa.NSIHeader(self.nsa_.urn(), provider_nsa.urn(), [])

                d = provider.terminate(header, sc_id)
                d.addCallbacks(
                    lambda c : log.msg('Succesfully terminated sub connection %s at %s after partial reservation failure.' % (sc_id, provider_nsa.urn()) , system=LOG_SYSTEM),
                    lambda f : log.msg('Error terminating connection after partial-reservation failure: %s' % str(f), system=LOG_SYSTEM)
                )
                defs.append(d)
            dl = defer.DeferredList(defs)
            yield dl
            yield state.terminated(conn)

            err = _createAggregateException(results, 'reservations', error.ConnectionCreateError)
            raise err


    @defer.inlineCallbacks
    def reserveCommit(self, header, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('ReserveCommit request. NSA: %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=LOG_SYSTEM)

        conn = yield self.getConnection(header.requester_nsa, connection_id)

        if conn.lifecycle_state == state.TERMINATED:
            raise error.ConnectionGoneError('Connection %s has been terminated' % connection_id)

        yield state.reserveCommit(conn)

        defs = []
        sub_connections = yield conn.SubConnections.get()
        for sc in sub_connections:
            # we assume a provider is available
            provider = self.getProvider(sc.provider_nsa)
            req_header = nsa.NSIHeader(self.nsa_.urn(), sc.provider_nsa, [])
            # we should probably mark as committing before sending message...
            d = provider.reserveCommit(req_header, sc.connection_id)
            defs.append(d)

        results = yield defer.DeferredList(defs, consumeErrors=True)

        successes = [ r[0] for r in results ]
        if all(successes):
            log.msg('Connection %s: ReserveCommit messages acked' % conn.connection_id, system=LOG_SYSTEM)
            defer.returnValue(connection_id)

        else:
            n_success = sum( [ 1 for s in successes if s ] )
            log.msg('Connection %s. Only %i of %i commit acked successfully' % (connection_id, n_success, len(defs)), system=LOG_SYSTEM)
            raise _createAggregateException(results, 'committed', error.ConnectionError)


    @defer.inlineCallbacks
    def reserveAbort(self, header, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('ReserveAbort request. NSA: %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=LOG_SYSTEM)

        conn = yield self.getConnection(header.requester_nsa, connection_id)

        if conn.lifecycle_state == state.TERMINATED:
            raise error.ConnectionGoneError('Connection %s has been terminated' % connection_id)

        yield state.reserveAbort(conn)

        save_defs = []
        defs = []
        sub_connections = yield conn.SubConnections.get()
        for sc in sub_connections:
            save_defs.append( state.reserveAbort(sc) )
            provider = self.getProvider(sc.provider_nsa)
            header = nsa.NSIHeader(self.nsa_.urn(), sc.provider_nsa, [])
            d = provider.reserveAbort(header, sc.connection_id)
            defs.append(d)

        yield defer.DeferredList(save_defs, consumeErrors=True)

        results = yield defer.DeferredList(defs, consumeErrors=True)

        successes = [ r[0] for r in results ]
        if all(successes):
            log.msg('Connection %s: All ReserveAbort acked' % conn.connection_id, system=LOG_SYSTEM)
            defer.returnValue(connection_id)

        else:
            n_success = sum( [ 1 for s in successes if s ] )
            log.msg('Connection %s. Only %i of %i connections aborted' % (self.connection_id, len(n_success), len(defs)), system=LOG_SYSTEM)
            raise self._createAggregateException(results, 'aborted', error.ConnectionError)


    @defer.inlineCallbacks
    def provision(self, header, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('Provision request. NSA: %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=LOG_SYSTEM)

        conn = yield self.getConnection(header.requester_nsa, connection_id)

        if conn.lifecycle_state == state.TERMINATED:
            raise error.ConnectionGoneError('Connection %s has been terminated' % connection_id)

        yield state.provisioning(conn)

        save_defs = []
        defs = []
        sub_connections = yield conn.SubConnections.get()
        for sc in sub_connections:
            save_defs.append( state.provisioning(sc) )
            provider = self.getProvider(sc.provider_nsa)
            header = nsa.NSIHeader(self.nsa_.urn(), sc.provider_nsa, [])
            d = provider.provision(header, sc.connection_id)
            defs.append(d)

        yield defer.DeferredList(save_defs, consumeErrors=True)

        results = yield defer.DeferredList(defs, consumeErrors=True)
        successes = [ r[0] for r in results ]
        if all(successes):
            # this just means we got an ack from all children
            defer.returnValue(connection_id)
        else:
            n_success = sum( [ 1 for s in successes if s ] )
            log.msg('Connection %s. Provision failure. %i of %i connections successfully acked' % (connection_id, n_success, len(defs)), system=LOG_SYSTEM)
            raise _createAggregateException(results, 'provision', error.ConnectionError)


    @defer.inlineCallbacks
    def release(self, header, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('Release request. NSA: %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=LOG_SYSTEM)

        conn = yield self.getConnection(header.requester_nsa, connection_id)

        if conn.lifecycle_state == state.TERMINATED:
            raise error.ConnectionGoneError('Connection %s has been terminated' % connection_id)

        yield state.releasing(conn)

        save_defs = []
        defs = []
        sub_connections = yield conn.SubConnections.get()
        for sc in sub_connections:
            save_defs.append( state.releasing(sc) )
            provider = self.getProvider(sc.provider_nsa)
            header = nsa.NSIHeader(self.nsa_.urn(), sc.provider_nsa, [])
            d = provider.release(header, sc.connection_id)
            defs.append(d)

        yield defer.DeferredList(save_defs, consumeErrors=True)

        results = yield defer.DeferredList(defs, consumeErrors=True)
        successes = [ r[0] for r in results ]
        if all(successes):
            # got ack from all children
            defer.returnValue(connection_id)

        else:
            n_success = sum( [ 1 for s in successes if s ] )
            log.msg('Connection %s. Only %i of %i connections successfully released' % (self.connection_id, n_success, len(defs)), system=LOG_SYSTEM)
            raise self._createAggregateException(results, 'release', error.ConnectionError)


    @defer.inlineCallbacks
    def terminate(self, header, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('Terminate request. NSA: %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=LOG_SYSTEM)

        conn = yield self.getConnection(header.requester_nsa, connection_id)

        if conn.lifecycle_state == state.TERMINATED:
            defer.returnValue(connection_id) # all good

        yield state.terminating(conn)

        defs = []
        sub_connections = yield conn.SubConnections.get()
        for sc in sub_connections:
            # we assume a provider is available
            provider = self.getProvider(sc.provider_nsa)
            header = nsa.NSIHeader(self.nsa_.urn(), sc.provider_nsa, [])
            d = provider.terminate(header, sc.connection_id)
            defs.append(d)

        results = yield defer.DeferredList(defs, consumeErrors=True)

        successes = [ r[0] for r in results ]
        if all(successes):
            yield state.terminated(conn)
            log.msg('Connection %s: Terminate succeeded' % conn.connection_id, system=LOG_SYSTEM)
            log.msg('Connection %s: All sub connections(%i) terminated' % (conn.connection_id, len(defs)), system=LOG_SYSTEM)
        else:
            # we are now in an inconsistent state...
            n_success = sum( [ 1 for s in successes if s ] )
            log.msg('Connection %s. Only %i of %i connections successfully terminated' % (conn.connection_id, n_success, len(defs)), system=LOG_SYSTEM)
            raise _createAggregateException(results, 'terminate', error.ConnectionError)

        defer.returnValue(connection_id)


    @defer.inlineCallbacks
    def querySummary(self, header, connection_ids=None, global_reservation_ids=None):

        log.msg('QuerySummary request from %s' % (header.requester_nsa), system=LOG_SYSTEM)

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
                sub_conns = yield c.SubConnections.get()

                source_stp = nsa.STP(c.source_network, c.source_port, c.source_labels)
                dest_stp = nsa.STP(c.dest_network, c.dest_port, c.dest_labels)
                criteria = nsa.ServiceParameters(c.start_time, c.end_time, source_stp, dest_stp, c.bandwidth, version=c.revision)

                aggr_active     = all( [ sc.data_plane_active     for sc in sub_conns ] )
                aggr_version    = max( [ sc.data_plane_version    for sc in sub_conns ] ) or 0 # can be None otherwise
                aggr_consistent = all( [ sc.data_plane_consistent for sc in sub_conns ] )
                data_plane_status = (aggr_active, aggr_version, aggr_consistent)

                states = (c.reservation_state, c.provision_state, c.lifecycle_state, data_plane_status)
                t = ( c.connection_id, c.global_reservation_id, c.description, [ criteria ], c.requester_nsa, states, self.getNotificationId())
                reservations.append(t)

            self.parent_requester.querySummaryConfirmed(header, reservations)

        except Exception as e:
            log.msg('Error during querySummary request: %s' % str(e), system=LOG_SYSTEM)


    def queryRecursive(self, header, connection_ids, global_reservation_ids):
        raise NotImplementedError('queryRecursive not yet implemented in aggregator')

    def queryNotification(self, header, connection_id, start_notification, end_notification):
        raise NotImplementedError('queryNotification not yet implemented in aggregator')

    # --
    # Requester API
    # --

    @defer.inlineCallbacks
    def reserveConfirmed(self, header, connection_id, global_reservation_id, description, criteria):

        log.msg('', system=LOG_SYSTEM)
        log.msg('reserveConfirm. NSA: %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=LOG_SYSTEM)

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

        # check that path matches our intent
        if criteria.source_stp.network != resv_info['source_network']:
            print "source network mismatch"
        if criteria.source_stp.port    != resv_info['source_port']:
            print "source port mismatch"
        if criteria.dest_stp.network   != resv_info['dest_network']:
            print "source network mismatch"
        if criteria.dest_stp.port      != resv_info['dest_port']:
            print "source port mismatch"
        if not criteria.source_stp.labels[0].singleValue():
            print "source label is no a single value"
        if not criteria.source_stp.labels[0].singleValue():
            print "dest label is no a single value"

        # skip label check for now
        #criteria.source_stp.labels[0].intersect(sub_connection.source_labels[0])
        #criteria.dest_stp.labels[0].intersect(sub_connection.dest_labels[0])

        # save sub connection in database
        sc = database.SubConnection(provider_nsa=org_provider_nsa, connection_id=connection_id, local_link=False, # remove local link sometime
                                    revision=criteria.version, service_connection_id=resv_info['service_connection_id'], order_id=resv_info['order_id'],
                                    global_reservation_id=global_reservation_id, description=description,
                                    reservation_state=state.RESERVE_HELD, provision_state=state.RELEASED, lifecycle_state=state.CREATED, data_plane_active=False,
                                    source_network=criteria.source_stp.network, source_port=criteria.source_stp.port, source_labels=criteria.source_stp.labels,
                                    dest_network=criteria.dest_stp.network, dest_port=criteria.dest_stp.port, dest_labels=criteria.dest_stp.labels,
                                    start_time=criteria.start_time.isoformat(), end_time=criteria.end_time.isoformat(), bandwidth=criteria.bandwidth)

        yield sc.save()

        # figure out if we can aggregate upwards

        conn = yield sc.ServiceConnection.get()
        sub_conns = yield conn.SubConnections.get()

        if sc.order_id == 0:
            conn.source_labels = criteria.source_stp.labels
        if sc.order_id == len(sub_conns)-1:
            conn.dest_labels = criteria.dest_stp.labels

        yield conn.save()

        if all( [ sc.reservation_state == state.RESERVE_HELD for sc in sub_conns ] ):
            log.msg('Connection %s: All sub connections reserve held, can emit reserveConfirmed' % (conn.connection_id), system=LOG_SYSTEM)
            yield state.reserveHeld(conn)
            header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn(), None)
            # construct criteria..
            source_stp = nsa.STP(conn.source_network, conn.source_port, conn.source_labels)
            dest_stp   = nsa.STP(conn.dest_network,   conn.dest_port,   conn.dest_labels)
            criteria = nsa.ServiceParameters(conn.start_time, conn.end_time, source_stp, dest_stp, conn.bandwidth)
            self.parent_requester.reserveConfirmed(header, conn.connection_id, conn.global_reservation_id, conn.description, criteria)

        else:
            log.msg('Connection %s: Still missing reserveConfirmed messages before emitting to parent' % (conn.connection_id), system=LOG_SYSTEM)


    @defer.inlineCallbacks
    def reserveCommitConfirmed(self, header, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('ReserveCommit Confirmed for sub connection %s. NSA %s ' % (connection_id, header.provider_nsa), system=LOG_SYSTEM)

        sub_connection = yield self.getSubConnection(header.provider_nsa, connection_id)
        sub_connection.reservation_state = state.RESERVE_START
        yield sub_connection.save()

        conn = yield sub_connection.ServiceConnection.get()
        sub_conns = yield conn.SubConnections.get()

        if all( [ sc.reservation_state == state.RESERVE_START for sc in sub_conns ] ):
            yield state.reserved(conn)
            header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn(), None)
            self.parent_requester.reserveCommitConfirmed(header, conn.connection_id)


    @defer.inlineCallbacks
    def reserveAbortConfirmed(self, header, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('ReserveAbort confirmed for sub connection %s. NSA %s ' % (connection_id, header.provider_nsa), system=LOG_SYSTEM)

        sub_connection = yield self.getSubConnection(header.provider_nsa, connection_id)
        sub_connection.reservation_state = state.RESERVE_START
        yield sub_connection.save()

        conn = yield sub_connection.ServiceConnection.get()
        sub_conns = yield conn.SubConnections.get()

        if all( [ sc.reservation_state == state.RESERVE_START for sc in sub_conns ] ):
            yield state.reserved(conn)
            header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn(), None)
            self.parent_requester.reserveAbortConfirmed(header, conn.connection_id)


    @defer.inlineCallbacks
    def provisionConfirmed(self, header, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('Provision Confirmed for sub connection %s. NSA %s ' % (connection_id, header.provider_nsa), system=LOG_SYSTEM)

        sub_connection = yield self.getSubConnection(header.provider_nsa, connection_id)
        yield state.provisioned(sub_connection)
        yield sub_connection.save()

        conn = yield sub_connection.ServiceConnection.get()
        sub_conns = yield conn.SubConnections.get()

        if all( [ sc.provision_state == state.PROVISIONED for sc in sub_conns ] ):
            yield state.provisioned(conn)
            req_header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn(), None)
            self.parent_requester.provisionConfirmed(req_header, conn.connection_id)


    @defer.inlineCallbacks
    def releaseConfirmed(self, header, connection_id):

        log.msg('', system=LOG_SYSTEM)
        log.msg('Release confirmed for sub connection %s. NSA %s ' % (connection_id, header.provider_nsa), system=LOG_SYSTEM)

        sub_connection = yield self.getSubConnection(header.provider_nsa, connection_id)
        yield state.released(sub_connection)
        yield sub_connection.save()

        conn = yield sub_connection.ServiceConnection.get()
        sub_conns = yield conn.SubConnections.get()

        if all( [ sc.provision_state == state.RELEASED for sc in sub_conns ] ):
            yield state.released(conn)
            req_header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn(), None)
            self.parent_requester.releaseConfirmed(req_header, conn.connection_id)


    @defer.inlineCallbacks
    def terminateConfirmed(self, header, connection_id):

        sub_connection = yield self.getSubConnection(header.provider_nsa, connection_id)
        sub_connection.reservation_state = state.TERMINATED
        yield sub_connection.save()

        conn = yield sub_connection.ServiceConnection.get()
        sub_conns = yield conn.SubConnections.get()

        if all( [ sc.reservation_state == state.TERMINATED for sc in sub_conns ] ):
            yield state.terminated(conn) # we always allow, even though the canonical NSI state machine does not
            header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn(), None)
            self.parent_requester.terminateConfirmed(header, conn.connection_id)

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
    def findSubConnection(self, provider_nsa, connection_id):

        sub_conns_match = yield database.SubConnection.findBy(connection_id=connection_id)

        if len(sub_conns_match) == 0:
            log.msg('No subconnection with id %s found' % connection_id)
        elif len(sub_conns_match) == 1:
            defer.returnValue(sub_conns_match[0])
        else:
            log.msg('More than one subconnection with id %s found.' % connection_id)
            raise NotImplementedError('Cannot handle that situation yet, as there is no matching on NSA yet')


    @defer.inlineCallbacks
    def reserveTimeout(self, header, connection_id, notification_id, timestamp, timeout_value, org_connection_id, org_nsa):

        sub_conn = yield self.findSubConnection(header.provider_nsa, connection_id)
        conn = yield sub_conn.ServiceConnection.get()
        sub_conns = yield conn.SubConnections.get()

        if len(sub_conns) == 1:
            log.msg("reserveTimeout: One sub connection for connection %s, notifying" % conn.connection_id)
            self.doTimeout(conn, timeout_value, org_connection_id, org_nsa)
        else:
            raise NotImplementedError('Cannot handle timeout for connection with more than one sub connection')


    @defer.inlineCallbacks
    def dataPlaneStateChange(self, header, connection_id, notification_id, timestamp, dps):

        active, version, consistent = dps
        log.msg("Data plane change for sub connection: %s Active: %s, version %i, consistent: %s" % \
                 (connection_id, active, version, consistent), system=LOG_SYSTEM)

        sub_conn = yield self.findSubConnection(header.provider_nsa, connection_id)

        sub_conn.data_plane_active      = active
        sub_conn.data_plane_version     = version
        sub_conn.data_plane_consistent  = consistent

        yield sub_conn.save()

        conn = yield sub_conn.ServiceConnection.get()
        sub_conns = yield conn.SubConnections.get()

        # do notification
        aggr_active     = all( [ sc.data_plane_active     for sc in sub_conns ] )
        aggr_version    = max( [ sc.data_plane_version    for sc in sub_conns ] )
        aggr_consistent = all( [ sc.data_plane_consistent for sc in sub_conns ] )

        header = nsa.NSIHeader(conn.requester_nsa, self.nsa_.urn(), reply_to=conn.requester_url)
        now = datetime.datetime.utcnow()
        data_plane_status = (aggr_active, aggr_version, aggr_consistent)
        log.msg("Connection %s: Aggregated data plane status: Active %s, version %i, consistent %s" % \
            (conn.connection_id, aggr_active, aggr_version, aggr_consistent), system=LOG_SYSTEM)

        self.parent_requester.dataPlaneStateChange(header, conn.connection_id, 0, now, data_plane_status)


    @defer.inlineCallbacks
    def errorEvent(self, header, connection_id, notification_id, timestamp, event, info, service_ex):

        # should mark sub connection as terminated / failed
        sub_conn = yield self.findSubConnection(header.provider_nsa, connection_id)
        conn = yield sub_conn.ServiceConnection.get()
        sub_conns = yield conn.SubConnections.get()

        if len(sub_conns) == 1:
            log.msg("reserveTimeout: One sub connection for connection %s, notifying" % conn.connection_id)
            self.doErrorEvent(conn, notification_id, event, info, service_ex)
        else:
            raise NotImplementedError('Cannot handle timeout for connection with more than one sub connection')


    def querySummaryConfirmed(self, header, summary_results):
        raise NotImplementedError('querySummaryConfirmed is not yet implemented in aggregater')

    def queryRecursiveConfirmed(self, header, recursive_results):
        raise NotImplementedError('queryRecursiveConfirmed is not yet implemented in aggregater')

    def queryNotificationFailed(self, header, service_exception):
        raise NotImplementedError('queryNotificationFailed is not yet implemented in aggregater')

