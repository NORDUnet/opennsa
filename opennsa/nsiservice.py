"""
OpenNSA NSI Service -> Backend adaptor (router).

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import uuid

from zope.interface import implements

from twisted.python import log, failure
from twisted.internet import reactor, defer, task

from opennsa.interface import NSIServiceInterface
from opennsa import nsa, error, registry, subscription, connection



LOG_SYSTEM = 'NSIService'



class NSIService:

    implements(NSIServiceInterface)

    def __init__(self, network, backend, service_registry, topology):
        self.network = network
        self.backend = backend
        self.service_registry = service_registry

        self.topology = topology

        # get own nsa from topology
        self.nsa = self.topology.getNetwork(self.network).nsa

        self.connections = {} # persistence, ha!

        self.service_registry.registerEventHandler(registry.RESERVE,   self.reserve,   registry.SYSTEM_SERVICE)
        self.service_registry.registerEventHandler(registry.PROVISION, self.provision, registry.SYSTEM_SERVICE)
        self.service_registry.registerEventHandler(registry.RELEASE,   self.release,   registry.SYSTEM_SERVICE)
        self.service_registry.registerEventHandler(registry.TERMINATE, self.terminate, registry.SYSTEM_SERVICE)
        self.service_registry.registerEventHandler(registry.QUERY,     self.query,     registry.SYSTEM_SERVICE)


    # utility functionality

    def getConnection(self, requester_nsa, connection_id):

        conn = self.connections.get(requester_nsa, {}).get(connection_id, None)
        if conn is None:
            raise error.ConnectionNonExistentError('No connection with id %s for NSA with address %s' % (connection_id, requester_nsa))
        else:
            return conn


    def setupSubConnection(self, link, conn, service_parameters):

        sub_sps = service_parameters.subConnectionClone(link.sourceSTP(), link.destSTP())

        # should check for local network
        if link.network == self.network:
            # resolve nrm ports from the topology

            # nsi2, at some point we need to move label selection into backend for now we keep it here
            if len(link.src_labels) == 0:
                raise error.TopologyError('Source STP must specify a label')
            if len(link.dst_labels) == 0:
                raise error.TopologyError('Dest STP must specify a label')
            if len(link.src_labels) > 1:
                raise error.TopologyError('Source STP specifies more than one label. Only one label is currently supported')
            if len(link.dst_labels) > 1:
                raise error.TopologyError('Dest STP specifies more than one label. Only one label is currently supported')

            src_label = link.src_labels[0]
            dst_label = link.dst_labels[0]
            # choose a label to use :-)
            src_label_value = str( src_label.randomLabel() )
            dst_label_value = str( dst_label.randomLabel() )

            nrm_src_port = self.topology.getNetwork(self.network).getInterface(link.src_port) + '.' + src_label_value
            nrm_dst_port = self.topology.getNetwork(self.network).getInterface(link.dst_port) + '.' + dst_label_value

            # update the connection service params to say which label was choosen here
            sub_sps.source_stp.labels = [ nsa.Label(src_label.type_, src_label_value) ]
            sub_sps.dest_stp.labels   = [ nsa.Label(dst_label.type_, dst_label_value) ]

            sub_conn = self.backend.createConnection(nrm_src_port, nrm_dst_port, sub_sps)

        else:
            sub_conn_id = 'urn:uuid:' + str(uuid.uuid1())
            remote_nsa = self.topology.getNetwork(link.network).nsa
            sub_conn = connection.SubConnection(self.service_registry, self.nsa, remote_nsa, conn, sub_conn_id, link.sourceSTP(), link.destSTP(), sub_sps)

        return sub_conn


    # command functionality

    def reserve(self, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters, sub):

        # --

        log.msg('', system=LOG_SYSTEM)
        log.msg('Connection %s. Reserve request from %s.' % (connection_id, requester_nsa), system=LOG_SYSTEM)

        if connection_id in self.connections.get(requester_nsa, {}):
            return defer.fail(error.ConnectionExistsError('Connection with id %s already exists' % connection_id))

        source_stp = service_parameters.source_stp
        dest_stp   = service_parameters.dest_stp

        # check that we know the networks
        self.topology.getNetwork(source_stp.network)
        self.topology.getNetwork(dest_stp.network)

        if source_stp == dest_stp:
            return defer.fail(error.TopologyError('Cannot connect %s to itself.' % source_stp))

        # since STPs are candidates here, we need to change these later on
        conn = connection.Connection(self.service_registry, requester_nsa, connection_id, source_stp, dest_stp, service_parameters, global_reservation_id, description)

        self.connections.setdefault(requester_nsa, {})[conn.connection_id] = conn

        # figure out nature of request

        path_info = ( connection_id, source_stp.network, source_stp.port, dest_stp.network, dest_stp.port, self.network)

        if source_stp.network == self.network and dest_stp.network == self.network:
            local_path_info = ( connection_id, self.network, source_stp.port, source_stp.labels, dest_stp.port, dest_stp.labels)
            log.msg('Connection %s: Local link creation: %s %s#%s -> %s#%s' % local_path_info, system=LOG_SYSTEM)
            link = nsa.Link(self.network, source_stp.port, dest_stp.port, source_stp.orientation, dest_stp.orientation,
                            source_stp.labels, dest_stp.labels)
            sc = self.setupSubConnection(link, conn, service_parameters)

            conn.source_stp.labels = sc.service_parameters.source_stp.labels
            conn.dest_stp.labels   = sc.service_parameters.dest_stp.labels
            conn.sub_connections.append(sc)

        # This code is for chaining requests and is currently not used, but might be needed sometime in the future
        # Once we get proper a topology service, some chaining will be necessary.

        #elif source_stp.network == self.network:
        #    # make path and chain on - common chaining
        #    log.msg('Reserve %s: Common chain creation: %s:%s -> %s:%s (%s)' % path_info, system=LOG_SYSTEM)
        #    paths = self.topology.findPaths(source_stp, dest_stp)
        #    # check for no paths
        #    paths.sort(key=lambda e : len(e.endpoint_pairs))
        #    selected_path = paths[0] # shortest path
        #    log.msg('Attempting to create path %s' % selected_path, system=LOG_SYSTEM)
        #    assert selected_path.source_stp.network == self.network
        #   # setup connection data - does this work with more than one hop?
        #    setupSubConnection(selected_path.source_stp, selected_path.endpoint_pairs[0].sourceSTP(), conn)
        #    setupSubConnection(selected_path.endpoint_pairs[0].destSTP(), dest_stp, conn)
        #elif dest_stp.network == self.network:
        #    # make path and chain on - backwards chaining
        #    log.msg('Backwards chain creation %s: %s:%s -> %s:%s (%s)' % path_info, system=LOG_SYSTEM)
        #    paths = self.topology.findPaths(source_stp, dest_stp)
        #    # check for no paths
        #    paths.sort(key=lambda e : len(e.endpoint_pairs))
        #    selected_path = paths[0] # shortest path
        #    log.msg('Attempting to create path %s' % selected_path, system=LOG_SYSTEM)
        #    assert selected_path.dest_stp.network == self.network
        #   # setup connection data
        #    setupSubConnection(selected_path.source_stp, selected_path.endpoint_pairs[0].sourceSTP(), conn)
        #    setupSubConnection(selected_path.endpoint_pairs[0].destSTP(), dest_stp, conn)
        #else:
        #    log.msg('Tree creation %s:  %s:%s -> %s:%s (%s)' % path_info, system=LOG_SYSTEM)


        # create the connection in tree/fanout style
        else:
            # log about creation and the connection type
            log.msg('Connection %s: Aggregate path creation: %s:%s -> %s:%s (%s)' % path_info, system=LOG_SYSTEM)
            # making the connection is the same for all though :-)
            paths = self.topology.findPaths(source_stp, dest_stp)

            # error out if we could not find a path
            if not paths:
                error_msg = 'Could not find a path for route %s:%s -> %s:%s' % (source_stp.network, source_stp.port, dest_stp.network, dest_stp.port)
                log.msg(error_msg, system=LOG_SYSTEM)
                raise error.TopologyError(error_msg)

            # check for no paths
            paths.sort(key=lambda e : len(e.links()))
            selected_path = paths[0] # shortest path
            log.msg('Attempting to create path %s' % selected_path, system=LOG_SYSTEM)

            for link in selected_path.links():
                # fixme, need to set end labels here
                sc = self.setupSubConnection(link, conn, service_parameters)
                conn.sub_connections.append(sc)


        def reserveResponse(result):
            success = False if isinstance(result, failure.Failure) else True
            if not success:
                log.msg('Error reserving: %s' % result.getErrorMessage(), system=LOG_SYSTEM)
            d = subscription.dispatchNotification(success, result, sub, self.service_registry)


        # now reserve connections needed to create path
        d = task.deferLater(reactor, 0, conn.reserve)
        d.addBoth(reserveResponse)
        return defer.succeed(None)


    def provision(self, requester_nsa, provider_nsa, session_security_attr, connection_id, sub):

        def provisionResponse(result):
            success = False if isinstance(result, failure.Failure) else True
            if not success:
                log.msg('Error provisioning: %s' % result.getErrorMessage(), system=LOG_SYSTEM)
            d = subscription.dispatchNotification(success, result, sub, self.service_registry)

        log.msg('', system=LOG_SYSTEM)
        # security check here

        conn = self.getConnection(requester_nsa, connection_id)
        d = task.deferLater(reactor, 0, conn.provision)
        d.addBoth(provisionResponse)
        return defer.succeed(None)


    def release(self, requester_nsa, provider_nsa, session_security_attr, connection_id, sub):

        def releaseResponse(result):
            success = False if isinstance(result, failure.Failure) else True
            if not success:
                log.msg('Error releasing: %s' % result.getErrorMessage(), system=LOG_SYSTEM)
            d = subscription.dispatchNotification(success, result, sub, self.service_registry)

        log.msg('', system=LOG_SYSTEM)
        # security check here

        conn = self.getConnection(requester_nsa, connection_id)
        d = task.deferLater(reactor, 0, conn.release)
        d.addBoth(releaseResponse)
        return defer.succeed(None)


    def terminate(self, requester_nsa, provider_nsa, session_security_attr, connection_id, sub):

        def terminateResponse(result):
            success = False if isinstance(result, failure.Failure) else True
            if not success:
                log.msg('Error terminating: %s' % result.getErrorMessage(), system=LOG_SYSTEM)
            d = subscription.dispatchNotification(success, result, sub, self.service_registry)

        log.msg('', system=LOG_SYSTEM)
        # security check here

        conn = self.getConnection(requester_nsa, connection_id)
        d = task.deferLater(reactor, 0, conn.terminate)
        d.addBoth(terminateResponse)
        return defer.succeed(None)


    def query(self, requester_nsa, provider_nsa, session_security_attr, operation, connection_ids, global_reservation_ids, sub):

        # security check here

        conns = []
        if connection_ids is None and global_reservation_ids is None:
            match = lambda conn : True
        else:
            match = lambda conn : conn.connection_id in connection_ids if connection_ids is not None else False or \
                                  conn.global_reservation_id in global_reservation_ids if global_reservation_ids is not None else False

        # This hack can be removed after SC11
        if requester_nsa == 'urn:ogf:network:nsa:OpenNSA-querier':
            # Be less noisy, query is something that happens fairly often.
            #log.msg('Enabling special demo query support for querier: %s' % (requester_nsa), system=LOG_SYSTEM)
            for connections in self.connections.values():
                for conn in connections.values():
                    if match(conn):
                        conns.append(conn)

        else:
            for conn in self.connections.get(requester_nsa, {}).values():
                if match(conn):
                    conns.append(conn)

        if not sub.match(registry.QUERY_RESPONSE):
            log.msg('Got query request with non-query response subscription')
        else:
            d = subscription.dispatchNotification(True, conns, sub, self.service_registry)

        return defer.succeed(None)

