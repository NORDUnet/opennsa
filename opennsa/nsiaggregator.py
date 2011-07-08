"""
OpenNSA NSI Service -> Backend adaptor (router).

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import random

from zope.interface import implements

from twisted.python import log
from twisted.internet import defer

from opennsa.interface import NSIServiceInterface
from opennsa import nsa, error, topology, jsonrpc, proxy, connection



class NSIAggregator:

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

#        log.msg("Reserve request: %s, %s, %s" % (connection_id, global_reservation_id, description))

        nsa_identity = requester_nsa.address

        if connection_id in self.connections.get(nsa_identity, {}):
            raise error.ReserveError('Reservation with connection id %s already exists' % connection_id)

        source_stp = service_parameters.source_stp
        dest_stp   = service_parameters.dest_stp

        conn = connection.Connection(connection_id, source_stp, dest_stp, global_reservation_id)

        def reservationMade(results):

            local_conn = results[0][1]

            conn.switchState(connection.RESERVED)
            self.connections.setdefault(nsa_identity, {})[connection_id] = conn
            log.msg('Reservation created. Connection id: %s (%s). Global id %s' % (connection_id, local_conn.internal_reservation_id, global_reservation_id), system='opennsa.NSIAggregator')
            return conn.connection_id


        def localReservationMade(local_conn):
            # should we do anything here..?
            return local_conn

        # figure out nature of request

        link_info = ( connection_id, source_stp.network, source_stp.endpoint, dest_stp.network, dest_stp.endpoint, self.network)

        if source_stp.network == self.network and dest_stp.network == self.network:
            log.msg('Reserve %s: Simple link creation: %s:%s -> %s:%s (%s)' % link_info, system='opennsa.NSIAggregator')
            # make an internal link, no sub requests

            local_conn = connection.LocalConnection(source_stp.endpoint, dest_stp.endpoint, backend=self.backend)

            conn.local_connection = local_conn
            conn.switchState(connection.RESERVING)

            d = local_conn.reserve(service_parameters)
            d.addCallback(localReservationMade)

            dl = defer.DeferredList( [ d ] )
            dl.addCallback(reservationMade)
            return dl

        elif source_stp.network == self.network:
            # make link and chain on - common chaining
            log.msg('Reserve %s: Common chain creation: %s:%s -> %s:%s (%s)' % link_info, system='opennsa.NSIAggregator')

            links = self.topology.findLinks(source_stp, dest_stp)
            # check for no links
            links.sort(key=lambda e : len(e.endpoint_pairs))
            selected_link = links[0] # shortest link
            log.msg('Attempting to create link %s' % selected_link, system='opennsa.NSIAggregator')

            assert selected_link.source_stp.network == self.network

            chain_network = selected_link.endpoint_pairs[0].stp2.network

            conn.switchState(connection.RESERVING)

            def issueChainReservation(local_conn):

                def chainedReservationMade(sub_conn):
                    # do we need this for something?
                    return sub_conn

                sub_conn_id = 'int-ccid' + ''.join( [ str(int(random.random() * 10)) for _ in range(4) ] )

                new_source_stp      = selected_link.endpoint_pairs[0].stp2
                new_service_params  = nsa.ServiceParameters('', '', new_source_stp, dest_stp)

                sub_conn = connection.SubConnection(sub_conn_id, chain_network, new_source_stp, dest_stp, proxy=self.proxy)
                conn.sub_connections.append(sub_conn)

                d = sub_conn.reserve(new_service_params, global_reservation_id, description)
                d.addCallback(chainedReservationMade)
                d.addCallback(lambda sub_conn : [ (True, local_conn), (True, conn) ] )
                return d

            local_conn = connection.LocalConnection(selected_link.source_stp.endpoint, selected_link.endpoint_pairs[0].stp1.endpoint, backend=self.backend)

            conn.local_connection = local_conn

            d = local_conn.reserve(service_parameters) # should probably make a new service params...
            d.addCallback(localReservationMade)
            d.addCallback(issueChainReservation)
            d.addCallback(reservationMade)
            return d


        elif dest_stp.network == self.network:
            # make link and chain on - backwards chaining
            log.msg('Backwards chain creation: %s:%s -> %s:%s (%s)' % link_info, system='opennsa.NSIAggregator')
            raise NotImplementedError('Backwards chain reservation')


        else:
            log.msg('Tree creation:  %s:%s -> %s:%s (%s)' % link_info, system='opennsa.NSIAggregator')
            raise NotImplementedError('Tree reservation')



    def cancelReservation(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        def connectionCancelled(results):
            conn.switchState(connection.CANCELLED)
            successes = [ r[0] for r in results ]
            if all(successes):
                if len(successes) > 1:
                    log.msg('Connection %s and all sub connections(%i) cancelled' % (conn.connection_id, len(results)-1), system='opennsa.NSIAggregator')
                return conn.connection_id
            if any(successes):
                print "Partial cancelation, gahh"
            else:
                log.msg('Failed to cancel connection %s and all sub connections(%i)' % (conn.connection_id, len(results)-1), system='opennsa.NSIAggregator')


        conn = self.getConnection(requester_nsa, connection_id)

        conn.switchState(connection.CANCELLING)

        defs = []
        for sc in conn.connections():
            d = sc.cancelReservation()
            defs.append(d)

        dl = defer.DeferredList(defs)
        dl.addCallback(connectionCancelled)
        return dl


    def provision(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        def provisionComplete(results):
            conn.switchState(connection.PROVISIONED)
            if len(results) > 1:
                log.msg('Connection %s and all sub connections(%i) provisioned' % (connection_id, len(results)-1), system='opennsa.NSIAggregator')
            return connection_id

        conn = self.getConnection(requester_nsa, connection_id)

        conn.switchState(connection.PROVISIONING)

        defs = []
        for sc in conn.connections():
            d = sc.provision()
            defs.append(d)

        dl = defer.DeferredList(defs)
        dl.addCallback(provisionComplete)
        return dl


    def releaseProvision(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        def connectionReleased(results):
            conn.switchState(connection.RESERVED)
            if len(results) > 1:
                log.msg('Connection %s and all sub connections(%i) released' % (connection_id, len(results)-1), system='opennsa.NSIAggregator')
            return conn.connection_id

        conn = self.getConnection(requester_nsa, connection_id)
        conn.switchState(connection.RELEASING)

        defs = []
        for sc in conn.connections():
            d = sc.releaseProvision()
            defs.append(d)

        dl = defer.DeferredList(defs)
        dl.addCallback(connectionReleased)
        return dl


    def query(self, requester_nsa, provider_nsa, query_filter, session_security_attributes):

        log.msg('', system='opennsa.NSIAggregator')


