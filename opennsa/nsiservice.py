"""
OpenNSA NSI Service -> Backend adaptor (router).

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import uuid

from zope.interface import implements

from twisted.python import log
from twisted.internet import defer

from opennsa.interface import NSIServiceInterface
from opennsa import error, topology, proxy, connection


LOG_SYSTEM = 'opennsa.NSIService'


def _logError(err):
    log.msg(err.getErrorMessage(), system=LOG_SYSTEM)
    return err



class NSIService:

    implements(NSIServiceInterface)

    def __init__(self, network, backend, topology_file, client):
        self.network = network
        self.backend = backend

        self.topology = topology.parseGOLETopology(topology_file)

        # get own nsa from topology
        self.nsa = self.topology.getNetwork(self.network).nsa
        self.proxy = proxy.NSIProxy(client, self.nsa, self.topology)

        self.connections = {} # persistence, ha!

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
            assert conn.local_connection is None, 'Cannot have multiple local sub-connection in connection'
            conn.local_connection = self.backend.createConnection(source_ep.nrmPort(), dest_ep.nrmPort(), sub_sps)

        else:
            sub_conn_id = 'urn:uuid:' + str(uuid.uuid1())
            # FIXME should be setup with NSA context, not network
            sub_conn = connection.SubConnection(conn, sub_conn_id, source_ep.network, source_ep, dest_ep, sub_sps, proxy=self.proxy)
            conn.sub_connections.append(sub_conn)

        return conn


    # command functionality

    def reserve(self, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters):

        # --

        log.msg('', system='opennsa')
        log.msg('Connection %s. Reserve request from %s.' % (connection_id, requester_nsa), system=LOG_SYSTEM)

        if connection_id in self.connections.get(requester_nsa, {}):
            raise error.ReserveError('Connection with id %s already exists' % connection_id)

        source_stp = service_parameters.source_stp
        dest_stp   = service_parameters.dest_stp

        conn = connection.Connection(requester_nsa, connection_id, source_stp, dest_stp, service_parameters, global_reservation_id, description)

        self.connections.setdefault(requester_nsa, {})[conn.connection_id] = conn

        # figure out nature of request

        path_info = ( connection_id, source_stp.network, source_stp.endpoint, dest_stp.network, dest_stp.endpoint, self.network)

        try:
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
                paths.sort(key=lambda e : len(e.endpoint_pairs))
                selected_path = paths[0] # shortest path
                log.msg('Attempting to create path %s' % selected_path, system=LOG_SYSTEM)

                prev_source_stp = selected_path.source_stp

                for stp_pair in selected_path.endpoint_pairs:
                    self.setupSubConnection(prev_source_stp, stp_pair.stp1, conn, service_parameters)
                    prev_source_stp = stp_pair.stp2
                # last hop
                self.setupSubConnection(prev_source_stp, selected_path.dest_stp, conn, service_parameters)

        except Exception, e:
            log.msg('Error setting up connection: %s' % str(e), system=LOG_SYSTEM)
            return defer.fail(e)

        def logReserve(conn):
            log.msg('Connection %s: Reserve succeeded' % conn.connection_id, system=LOG_SYSTEM)
            return conn

        def logError(err):
            log.msg(err.getErrorMessage(), system=LOG_SYSTEM)
            return err

        # now reserve connections needed to create path
        d = conn.reserve()
        d.addCallbacks(logReserve, logError)
        return d


    def terminate(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        log.msg('', system=LOG_SYSTEM)
        # security check here

        try:
            conn = self.getConnection(requester_nsa, connection_id)
            d = conn.terminate()
            d.addErrback(_logError)
            return d
        except error.NoSuchConnectionError, e:
            log.msg('NSA %s requested non-existing connection %s' % (requester_nsa, connection_id), system=LOG_SYSTEM)
            return defer.fail(e)
        except Exception, e:
            log.msg('Unexpected error during terminate: %s' % str(e), system=LOG_SYSTEM)
            return defer.fail(e)


    def provision(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        log.msg('', system=LOG_SYSTEM)
        # security check here

        try:
            conn = self.getConnection(requester_nsa, connection_id)
            d = conn.provision()
            d.addErrback(_logError)
            return d
        except error.NoSuchConnectionError, e:
            log.msg('NSA %s requested non-existing connection %s' % (requester_nsa, connection_id), system=LOG_SYSTEM)
            return defer.fail(e)
        except Exception, e:
            log.msg('Unexpected error during provision: %s' % str(e), system=LOG_SYSTEM)
            return defer.fail(e)


    def release(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        log.msg('', system=LOG_SYSTEM)
        # security check here

        try:
            conn = self.getConnection(requester_nsa, connection_id)
            d = conn.release()
            d.addErrback(_logError)
            return d
        except error.NoSuchConnectionError, e:
            log.msg('NSA %s requested non-existing connection %s' % (requester_nsa, connection_id), system=LOG_SYSTEM)
            return defer.fail(e)
        except Exception, e:
            log.msg('Unexpected error during release: %s' % str(e), system=LOG_SYSTEM)
            return defer.fail(e)


    def query(self, requester_nsa, provider_nsa, session_security_attr, operation, connection_ids=None, global_reservation_ids=None):

        # security check here

        try:
            conns = []
            if connection_ids is None and global_reservation_ids is None:
                match = lambda conn : True
            else:
                match = lambda conn : conn.connection_id in connection_ids if connection_ids is not None else False or \
                                      conn.global_reservation_id in global_reservation_ids if global_reservation_ids is not None else False

            if requester_nsa == 'urn:ogf:network:nsa:OpenNSA-querier':
                log.msg('Enabling special demo query support for querier: %s' % (requester_nsa), system=LOG_SYSTEM)
                for connections in self.connections.values():
                    for conn in connections.values():
                        if match(conn):
                            conns.append(conn)

            else:
                for conn in self.connections.get(requester_nsa, {}).values():
                    if match(conn):
                        conns.append(conn)

            return defer.succeed(conns)

        except Exception, e:
            log.msg('Unexpected error during query: %s' % str(e), system=LOG_SYSTEM)
            return defer.fail(e)

