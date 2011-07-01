"""
OpenNSA NSI Service -> Backend adaptor (router).

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from zope.interface import implements

from twisted.python import log

from opennsa.interface import NSIServiceInterface
from opennsa import nsa, error, topology, jsonrpc



class NSIAggregator:

    implements(NSIServiceInterface)

    def __init__(self, network, backend, topology_file):
        self.network = network
        self.backend = backend

        self.topology = topology.Topology()
        self.topology.parseTopology(open(topology_file))

        self.connections = {}


    def reserve(self, requester_nsa, provider_nsa, connection_id, global_reservation_id, description, service_parameters, session_security_attributes):

#        log.msg("Reserve request: %s, %s, %s" % (connection_id, global_reservation_id, description))

        nsa_identity = requester_nsa.address

        if connection_id in self.connections.get(nsa_identity, {}):
            raise error.ReserveError('Reservation with connection id %s already exists' % connection_id)

        source_stp = service_parameters.source_stp
        dest_stp   = service_parameters.dest_stp

        def reservationMade(internal_reservation_id, sub_reservations=None):
            #nsa_identity = requester_nsa.address
            self.connections.setdefault(nsa_identity, {})
            conn = nsa.Connection(connection_id, internal_reservation_id, source_stp, dest_stp, global_reservation_id, sub_reservations)
            self.connections[nsa_identity][connection_id] = conn
            return connection_id

        # figure out nature of request

        link_info = (source_stp.network, source_stp.endpoint, dest_stp.network, dest_stp.endpoint, self.network)

        if source_stp.network == self.network and dest_stp.network == self.network:
            log.msg('Simple link creation: %s:%s -> %s:%s (%s)' % link_info, system='opennsa.NSIAggregator')
            # make an internal link, no sub requests
            d = self.backend.reserve(source_stp.endpoint, dest_stp.endpoint, service_parameters)
            d.addCallback(reservationMade)
            return d

        elif source_stp.network == self.network:
            # make link and chain on - common chaining
            log.msg('Common chain creation: %s:%s -> %s:%s (%s)' % link_info, system='opennsa.NSIAggregator')

            links = self.topology.findLinks(source_stp.network, source_stp.endpoint, dest_stp.network, dest_stp.endpoint)
            # check for no links
            links.sort(key=lambda e : len(e.endpoint_pairs))
            shortest_link = links[0]
            log.msg('Attempting to create link %s' % shortest_link)

            assert shortest_link.source_network == self.network

            chain_network = shortest_link.endpoint_pairs[0][2]

            def issueChainReservation(connection_id):
                own_address = self.topology.getNetwork(self.network).nsa_address # is this ok? why not?
                own_nsa = nsa.NetworkServiceAgent(own_address, None)

                network_nsa_url = self.topology.getNetwork(chain_network).nsa_address
                chain_nsa = nsa.NetworkServiceAgent(network_nsa_url, None)

                conn_id = 'sager'

                new_source_stp      = nsa.STP(shortest_link.endpoint_pairs[0][2], shortest_link.endpoint_pairs[0][3] )
                new_service_params  = nsa.ServiceParameters('', '', new_source_stp, dest_stp)

                proxy = jsonrpc.JSONRPCNSIClient()
                d = proxy.reserve(own_nsa, chain_nsa, conn_id, global_reservation_id, description, new_service_params, None)
                d.addCallback(lambda e : connection_id)
                return d

            d = self.backend.reserve(shortest_link.source_endpoint, shortest_link.endpoint_pairs[0][1], service_parameters)
            d.addCallback(reservationMade)
            d.addCallback(issueChainReservation)
            return d



        elif dest_stp.network == self.network:
            # make link and chain on - backwards chaining
            log.msg('Backwards chain creation: %s:%s -> %s:%s (%s)' % link_info, system='opennsa.NSIAggregator')
            raise NotImplementedError('Backwards chain reservation')


        else:
            log.msg('Tree creation:  %s:%s -> %s:%s (%s)' % link_info, system='opennsa.NSIAggregator')
            raise NotImplementedError('Tree reservation')



    def cancelReservation(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        conn = self.connections.get(requester_nsa.address, {}).get(connection_id, None)
        if conn is None:
            raise error.CancelReservationError('No connection with id %s for NSA with address %s' % (connection_id, requester_nsa.address))
        # check state before cancelling

        def reservationCancelled(_):
            pass
            # update state

        d = self.backend.cancelReservation(conn.internal_reservation_id)
        return d


    def provision(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        conn = self.connections.get(requester_nsa.address, {}).get(connection_id, None)
        if conn is None:
            raise error.ProvisionError('No connection with id %s for NSA with address %s' % (connection_id, requester_nsa.address))
        # check state is ok before provisioning

        def provisionMade(internal_connection_id):
            conn.internal_connection_id = internal_connection_id
            # update state
            return connection_id

        # if there are any sub connections, call must be issues to those
        d = self.backend.provision(conn.internal_reservation_id)
        d.addCallback(provisionMade)
        return d


    def releaseProvision(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        conn = self.connections.get(requester_nsa.address, {}).get(connection_id, None)
        if conn is None:
            raise error.ReleaseProvisionError('No connection with id %s for NSA with address %s' % (connection_id, requester_nsa.address))

        def provisionReleased(internal_reservation_id):
            conn.internal_reservation_id = internal_reservation_id
            conn.internal_connection_id = None

        d = self.backend.releaseProvision(conn.internal_connection_id)
        d.addCallback(provisionReleased)
        return d


    def query(self, requester_nsa, provider_nsa, session_security_attributes):

        raise NotImplementedError('NSIService Query for Router adaptor not implemented.')


