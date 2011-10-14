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
from opennsa import nsa, error, topology, proxy, connection



def _logError(err):
    log.msg(err.getErrorMessage(), system='opennsa.NSIService')
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


    # command functionality

    def reservation(self, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters):

        def setupSubConnection(source_stp, dest_stp, conn, service_parameters):

            assert source_stp.network == dest_stp.network

            # should check for local network
            if source_stp.network == self.network:
                assert conn.local_connection is None
                conn.local_connection = self.backend.createConnection(source_stp.endpoint, dest_stp.endpoint, service_parameters)

            else:
                sub_conn_id = 'urn:uuid:' + str(uuid.uuid1())
                # FIXME should be setup with NSA context, not network
                sub_conn = connection.SubConnection(conn, sub_conn_id, source_stp.network, source_stp, dest_stp, proxy=self.proxy)
                conn.sub_connections.append(sub_conn)

            return conn

        # --

        log.msg('', system='opennsa')
        log.msg('Connection %s. Reservation request from %s.' % (connection_id, requester_nsa), system='opennsa.NSIService')

        if connection_id in self.connections.get(requester_nsa, {}):
            raise error.ReserveError('Connection with id %s already exists' % connection_id)

        source_stp = service_parameters.source_stp
        dest_stp   = service_parameters.dest_stp

        conn = connection.Connection(requester_nsa, connection_id, source_stp, dest_stp, global_reservation_id, description)

        self.connections.setdefault(requester_nsa, {})[conn.connection_id] = conn

        # figure out nature of request

        path_info = ( connection_id, source_stp.network, source_stp.endpoint, dest_stp.network, dest_stp.endpoint, self.network)

        try:
            if source_stp.network == self.network and dest_stp.network == self.network:
                log.msg('Connection %s: Simple path creation: %s:%s -> %s:%s (%s)' % path_info, system='opennsa.NSIService')

                setupSubConnection(source_stp, dest_stp, conn, service_parameters)

        # This code is for chaining requests and is currently not used, but might be needed sometime in the future
        # Once we get proper a topology service, some chaining will be necessary.

        #elif source_stp.network == self.network:
        #    # make path and chain on - common chaining
        #    log.msg('Reserve %s: Common chain creation: %s:%s -> %s:%s (%s)' % path_info, system='opennsa.NSIService')
        #    paths = self.topology.findPaths(source_stp, dest_stp)
        #    # check for no paths
        #    paths.sort(key=lambda e : len(e.endpoint_pairs))
        #    selected_path = paths[0] # shortest path
        #    log.msg('Attempting to create path %s' % selected_path, system='opennsa.NSIService')
        #    assert selected_path.source_stp.network == self.network
        #   # setup connection data - does this work with more than one hop?
        #    setupSubConnection(selected_path.source_stp, selected_path.endpoint_pairs[0].stp1, conn)
        #    setupSubConnection(selected_path.endpoint_pairs[0].stp2, dest_stp, conn)
        #elif dest_stp.network == self.network:
        #    # make path and chain on - backwards chaining
        #    log.msg('Backwards chain creation %s: %s:%s -> %s:%s (%s)' % path_info, system='opennsa.NSIService')
        #    paths = self.topology.findPaths(source_stp, dest_stp)
        #    # check for no paths
        #    paths.sort(key=lambda e : len(e.endpoint_pairs))
        #    selected_path = paths[0] # shortest path
        #    log.msg('Attempting to create path %s' % selected_path, system='opennsa.NSIService')
        #    assert selected_path.dest_stp.network == self.network
        #   # setup connection data
        #    setupSubConnection(selected_path.source_stp, selected_path.endpoint_pairs[0].stp1, conn)
        #    setupSubConnection(selected_path.endpoint_pairs[0].stp2, dest_stp, conn)
        #else:
        #    log.msg('Tree creation %s:  %s:%s -> %s:%s (%s)' % path_info, system='opennsa.NSIService')


            # create the connection in tree/fanout style
            else:
                # log about creation and the connection type
                log.msg('Connection %s: Aggregate path creation: %s:%s -> %s:%s (%s)' % path_info, system='opennsa.NSIService')
                # making the connection is the same for all though :-)
                paths = self.topology.findPaths(source_stp, dest_stp)

                # check for no paths
                paths.sort(key=lambda e : len(e.endpoint_pairs))
                selected_path = paths[0] # shortest path
                log.msg('Attempting to create path %s' % selected_path, system='opennsa.NSIService')

                prev_source_stp = source_stp

                for stp_pair in selected_path.endpoint_pairs:
                    setupSubConnection(prev_source_stp, stp_pair.stp1, conn)
                    prev_source_stp = stp_pair.stp2
                # last hop
                setupSubConnection(prev_source_stp, dest_stp, conn)

        except Exception, e:
            log.msg('Error setting up connection: %s' % str(e), system='opennsa.NSIService')
            return defer.fail(e)

        def logReservation(conn):
            log.msg('Connection %s: Reservation succeeded' % conn.connection_id, system='opennsa.NSIService')
            return conn

        def logError(err):
            log.msg(err.getErrorMessage())
            return err

        # now reserve connections needed to create path
        d = conn.reservation(service_parameters, requester_nsa)
        d.addCallbacks(logReservation, logError)
        return d


    def terminate(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        log.msg('', system='opennsa.NSIService')
        conn = self.getConnection(requester_nsa, connection_id)
        # security check here

        try:
            d = conn.terminate()
            d.addErrback(_logError)
            return d
        except Exception, e:
            log.msg('Unexpected error during terminate: %s' % str(e))
            return defer.fail(e)


    def provision(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        log.msg('', system='opennsa.NSIService')
        conn = self.getConnection(requester_nsa, connection_id)
        # security check here

        try:
            d = conn.provision()
            d.addErrback(_logError)
            return d
        except Exception, e:
            log.msg('Unexpected error during provision: %s' % str(e))
            return defer.fail(e)


    def release(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        log.msg('', system='opennsa.NSIService')
        conn = self.getConnection(requester_nsa, connection_id)
        # security check here

        try:
            d = conn.release()
            d.addErrback(_logError)
            return d
        except Exception, e:
            log.msg('Unexpected error during release: %s' % str(e))
            return defer.fail(e)


    def query(self, requester_nsa, provider_nsa, session_security_attr, operation, connection_ids=None, global_reservation_ids=None):

        # security check here

        try:
            conns = []
            if connection_ids is None and global_reservation_ids is None:
                match = lambda conn : True
            else:
                match = lambda conn : conn.connection_id in connection_ids if connection_ids is not None else False or \
                                      conn.global_reservation_id in global_reservation_ids if connection_ids is not None else False

            for conn in self.connections.get(requester_nsa, {}).values():
                if match(conn):
                    conns.append(conn)

            return defer.succeed(conns)

        except Exception, e:
            log.msg('Unexpected error during query: %s' % str(e))
            return defer.fail(e)

