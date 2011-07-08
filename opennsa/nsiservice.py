"""
OpenNSA NSI Service -> Backend adaptor (router).

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import random

from zope.interface import implements

from twisted.python import log

from opennsa.interface import NSIServiceInterface
from opennsa import error, topology, jsonrpc, proxy, connection



class NSIService:

    implements(NSIServiceInterface)

    def __init__(self, network, backend, topology_file):
        self.network = network
        self.backend = backend

        self.topology = topology.Topology()
        self.topology.parseTopology(open(topology_file))

        # get own nsa from topology
        self.nsa = self.topology.getNetwork(self.network).nsa
        self.proxy = proxy.NSIProxy(jsonrpc.JSONRPCNSIClient(), self.nsa, self.topology)

        self.connections = {} # persistence, ha!

    # utility functionality

    def getConnection(self, requester_nsa, connection_id):

        conn = self.connections.get(requester_nsa.address, {}).get(connection_id, None)
        if conn is None:
            raise error.NoSuchConnectionError('No connection with id %s for NSA with address %s' % (connection_id, requester_nsa.address))
        else:
            return conn


    # command functionality

    def reserve(self, requester_nsa, provider_nsa, connection_id, global_reservation_id, description, service_parameters, session_security_attributes):

        def setupSubConnection(source_stp, dest_stp, conn):

            assert source_stp.network == dest_stp.network

            # should check for local network
            if source_stp.network == self.network:
                local_conn = connection.LocalConnection(source_stp.endpoint, dest_stp.endpoint, backend=self.backend)
                assert conn.local_connection is None
                conn.local_connection = local_conn
            else:
                sub_conn_id = 'int-ccid' + ''.join( [ str(int(random.random() * 10)) for _ in range(4) ] )
                sub_conn = connection.SubConnection(sub_conn_id, source_stp.network, source_stp, dest_stp, proxy=self.proxy)
                conn.sub_connections.append(sub_conn)

            return conn


        def reservationMade(conn):
            self.connections.setdefault(nsa_identity, {})[connection_id] = conn
            return conn.connection_id

        # --

        nsa_identity = requester_nsa.address

        if connection_id in self.connections.get(nsa_identity, {}):
            raise error.ReserveError('Reservation with connection id %s already exists' % connection_id)

        source_stp = service_parameters.source_stp
        dest_stp   = service_parameters.dest_stp

        conn = connection.Connection(connection_id, source_stp, dest_stp, global_reservation_id, description)

        # figure out nature of request

        path_info = ( connection_id, source_stp.network, source_stp.endpoint, dest_stp.network, dest_stp.endpoint, self.network)

        if source_stp.network == self.network and dest_stp.network == self.network:
            log.msg('Reserve %s: Simple path creation: %s:%s -> %s:%s (%s)' % path_info, system='opennsa.NSIService')

            conn.local_connection = connection.LocalConnection(source_stp.endpoint, dest_stp.endpoint, backend=self.backend)

            dl = conn.reserve(service_parameters)
            dl.addCallback(reservationMade)

        elif source_stp.network == self.network:
            # make path and chain on - common chaining
            log.msg('Reserve %s: Common chain creation: %s:%s -> %s:%s (%s)' % path_info, system='opennsa.NSIService')

            paths = self.topology.findPaths(source_stp, dest_stp)
            # check for no paths
            paths.sort(key=lambda e : len(e.endpoint_pairs))
            selected_path = paths[0] # shortest path
            log.msg('Attempting to create path %s' % selected_path, system='opennsa.NSIService')

            assert selected_path.source_stp.network == self.network

            # setup connection data
            setupSubConnection(selected_path.source_stp, selected_path.endpoint_pairs[0].stp1, conn)
            setupSubConnection(selected_path.endpoint_pairs[0].stp2, dest_stp, conn)

            # create connection
            d = conn.reserve(service_parameters)
            d.addCallback(reservationMade)
            return d


        elif dest_stp.network == self.network:
            # make path and chain on - backwards chaining
            log.msg('Backwards chain creation %s: %s:%s -> %s:%s (%s)' % path_info, system='opennsa.NSIService')
            raise NotImplementedError('Backwards chain reservation')

        else:
            log.msg('Tree creation %s:  %s:%s -> %s:%s (%s)' % path_info, system='opennsa.NSIService')

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

            d = conn.reserve(service_parameters)
            d.addCallback(reservationMade)
            return d


    def cancelReservation(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        conn = self.getConnection(requester_nsa, connection_id)
        # security check here

        d = conn.cancelReservation()
        d.addCallback(lambda conn : conn.connection_id)
        return d


    def provision(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        conn = self.getConnection(requester_nsa, connection_id)
        # security check here

        d = conn.provision()
        d.addCallback(lambda conn : conn.connection_id)
        return d


    def releaseProvision(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        conn = self.getConnection(requester_nsa, connection_id)
        # security check here

        d = conn.releaseProvision()
        d.addCallback(lambda conn : conn.connection_id)
        return d


    def query(self, requester_nsa, provider_nsa, query_filter, session_security_attributes):

        log.msg('', system='opennsa.NSIService')


