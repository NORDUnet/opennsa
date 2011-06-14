"""
OpenNSA NSI Service -> Backend adaptor (router).

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from zope.interface import implements

from opennsa.interface import NSIServiceInterface



class NSIRouterAdaptor:

    implements(NSIServiceInterface)

    def __init__(self, network, backend):
        self.network = network
        self.backend = backend


    def reserve(self, requester_nsa, provider_nsa, reservation_id, description, connection_id,
                service_parameters, session_security_attributes):

        source_stp = service_parameters.source_stp
        dest_stp   = service_parameters.dest_stp

        if source_stp.network != self.network:
            raise ReserveError('Invalid source network')
        if dest_stp.network != self.network:
            raise ReserveError('Invalid dest network')
        if service_parameters.stps:
            raise ReserveError('Sub-connections cannot be specified in router adaptor')

        d = self.backend.reserve(source_stp.endpoint, dest_stp.endpoint, service_parameters)
        return d


    def cancelReservation(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        d = self.backend.cancelReservation(connection_id)
        return d


    def provision(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        d = self.backend.provision(connection_id)
        return d


    def releaseProvision(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        d = self.backend.releaseProvision(connection_id)
        return d


    def query(self, requester_nsa, provider_nsa, session_security_attributes):

        raise NotImplementedError('NSIService Query for Router adaptor not implemented.')


