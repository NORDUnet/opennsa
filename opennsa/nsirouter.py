"""
OpenNSA NSI Service -> Backend adaptor (router).

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from zope.interface import implements

from twisted.python import log

from opennsa.interface import NSIServiceInterface
from opennsa import error



class NSIRouterAdaptor:

    implements(NSIServiceInterface)

    def __init__(self, network, backend):
        self.network = network
        self.backend = backend
        self.reservation_mapping = {}


    def reserve(self, requester_nsa, provider_nsa, connection_id, global_reservation_id, description, service_parameters, session_security_attributes):

        log.msg("Reserve request: %s, %s, %s" % (connection_id, global_reservation_id, description))

        source_stp = service_parameters.source_stp
        dest_stp   = service_parameters.dest_stp

        if source_stp.network != self.network:
            raise error.ReserveError('Invalid source network')
        if dest_stp.network != self.network:
            raise error.ReserveError('Invalid dest network')
        if service_parameters.stps:
            raise error.ReserveError('Sub-connections cannot be specified in router adaptor')

        def reservationMade(internal_reservation_id):
            self.reservation_mapping[connection_id] = internal_reservation_id
            return connection_id

        d = self.backend.reserve(source_stp.endpoint, dest_stp.endpoint, service_parameters)
        #d.addCallback(lambda internal_reservation_id : reservation_id) # client should not get internal reservation id
        d.addCallback(reservationMade)
        return d


    def cancelReservation(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        d = self.backend.cancelReservation(connection_id)
        return d


    def provision(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        internal_reservation_id = self.reservation_mapping[connection_id]

        #d = self.backend.provision(connection_id)
        d = self.backend.provision(internal_reservation_id)
        d.addCallback(lambda internal_connection_id : connection_id)
        return d


    def releaseProvision(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        d = self.backend.releaseProvision(connection_id)
        return d


    def query(self, requester_nsa, provider_nsa, session_security_attributes):

        raise NotImplementedError('NSIService Query for Router adaptor not implemented.')


