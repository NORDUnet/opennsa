"""
OpenNSA NSI Service -> Backend adaptor (router).

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import uuid

from zope.interface import implements

from twisted.python import log
from twisted.internet import reactor, defer

from opennsa.interface import NSIServiceInterface
from opennsa import error, registry, subscription, connection



LOG_SYSTEM = 'opennsa.NSIService'



class NSIService:

    implements(NSIServiceInterface)

    def __init__(self, network, backend, service_registry, topology, client):
        self.network = network
        self.backend = backend
        self.service_registry = service_registry

        self.topology = topology

        # get own nsa from topology
        self.client = client
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
            raise error.NoSuchConnectionError('No connection with id %s for NSA with address %s' % (connection_id, requester_nsa))
        else:
            return conn


    def setupSubConnection(self, source_ep, dest_ep, conn, service_parameters):

        assert source_ep.network == dest_ep.network, 'Source and destination network differ in sub-connection'

        sub_sps = service_parameters.subConnectionClone(source_ep, dest_ep)

        # should check for local network
        if source_ep.network == self.network:
            sub_conn = self.backend.createConnection(source_ep.nrmPort(), dest_ep.nrmPort(), sub_sps)
        else:
            sub_conn_id = 'urn:uuid:' + str(uuid.uuid1())
            remote_nsa = self.topology.getNetwork(source_ep.network).nsa
            sub_conn = connection.SubConnection(self.client, self.nsa, remote_nsa, conn, sub_conn_id, source_ep, dest_ep, sub_sps)

        conn.sub_connections.append(sub_conn)

        return conn


    # command functionality

    def reserve(self, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters, sub):

        # --

        log.msg('', system='opennsa')
        log.msg('Connection %s. Reserve request from %s.' % (connection_id, requester_nsa), system=LOG_SYSTEM)

        if connection_id in self.connections.get(requester_nsa, {}):
            raise error.ReserveError('Connection with id %s already exists' % connection_id)

        source_stp = service_parameters.source_stp
        dest_stp   = service_parameters.dest_stp

        if source_stp == dest_stp:
            return defer.fail(error.ReserveError('Cannot connect %s to itself.' % source_stp))

        conn = connection.Connection(self.service_registry, requester_nsa, connection_id, source_stp, dest_stp, service_parameters, global_reservation_id, description)

        self.connections.setdefault(requester_nsa, {})[conn.connection_id] = conn

        # figure out nature of request

        path_info = ( connection_id, source_stp.network, source_stp.endpoint, dest_stp.network, dest_stp.endpoint, self.network)

        if source_stp.network == self.network and dest_stp.network == self.network:
            log.msg('Connection %s: Simple path creation: %s:%s -> %s:%s (%s)' % path_info, system=LOG_SYSTEM)

            # we need to resolve this from our topology in order to get any local configuration
            source_ep = self.topology.getEndpoint(self.network, source_stp.endpoint)
            dest_ep   = self.topology.getEndpoint(self.network, dest_stp.endpoint)
            self.setupSubConnection(source_ep, dest_ep, conn, service_parameters)

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
        #    setupSubConnection(selected_path.source_stp, selected_path.endpoint_pairs[0].stp1, conn)
        #    setupSubConnection(selected_path.endpoint_pairs[0].stp2, dest_stp, conn)
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
        #    setupSubConnection(selected_path.source_stp, selected_path.endpoint_pairs[0].stp1, conn)
        #    setupSubConnection(selected_path.endpoint_pairs[0].stp2, dest_stp, conn)
        #else:
        #    log.msg('Tree creation %s:  %s:%s -> %s:%s (%s)' % path_info, system=LOG_SYSTEM)


        # create the connection in tree/fanout style
        else:
            # log about creation and the connection type
            log.msg('Connection %s: Aggregate path creation: %s:%s -> %s:%s (%s)' % path_info, system=LOG_SYSTEM)
            # making the connection is the same for all though :-)
            paths = self.topology.findPaths(source_stp, dest_stp)

            # check for no paths
            paths.sort(key=lambda e : len(e.links()))
            selected_path = paths[0] # shortest path
            log.msg('Attempting to create path %s' % selected_path, system=LOG_SYSTEM)

            for link in selected_path.links():
                self.setupSubConnection(link.stp1, link.stp2, conn, service_parameters)

        # now reserve connections needed to create path
        conn.addSubscription(sub)
        reactor.callWhenRunning(conn.reserve)
        return defer.succeed(None)


    def provision(self, requester_nsa, provider_nsa, session_security_attr, connection_id, sub):

        log.msg('', system=LOG_SYSTEM)
        # security check here

        try:
            conn = self.getConnection(requester_nsa, connection_id)
            conn.addSubscription(sub)
            reactor.callWhenRunning(conn.provision)
            return defer.succeed(None)
        except error.NoSuchConnectionError, e:
            log.msg('NSA %s requested non-existing connection %s' % (requester_nsa, connection_id), system=LOG_SYSTEM)
            return defer.fail(e)


    def release(self, requester_nsa, provider_nsa, session_security_attr, connection_id, sub):

        log.msg('', system=LOG_SYSTEM)
        # security check here

        try:
            conn = self.getConnection(requester_nsa, connection_id)
            conn.addSubscription(sub)
            reactor.callWhenRunning(conn.release)
            return defer.succeed(None)
        except error.NoSuchConnectionError, e:
            log.msg('NSA %s requested non-existing connection %s' % (requester_nsa, connection_id), system=LOG_SYSTEM)
            return defer.fail(e)


    def terminate(self, requester_nsa, provider_nsa, session_security_attr, connection_id, sub):

        log.msg('', system=LOG_SYSTEM)
        # security check here

        try:
            conn = self.getConnection(requester_nsa, connection_id)
            conn.addSubscription(sub)
            reactor.callWhenRunning(conn.terminate)
            return defer.succeed(None)
        except error.NoSuchConnectionError, e:
            log.msg('NSA %s requested non-existing connection %s' % (requester_nsa, connection_id), system=LOG_SYSTEM)
            return defer.fail(e)


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

