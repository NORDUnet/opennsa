"""
Handy proxy wrapping for easier / shorter calls to NSI agents.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""



class NSIProxy:

    def __init__(self, client, nsa_id, topology):
        self.client     = client    # client adhering to the NSIInterface
        self.nsa_id     = nsa_id    # this is the identity of the caller
        self.topology   = topology  # used for network -> nsa lookups


    def reserve(self, network, connection_id, global_reservation_id, description, service_parameters, session_security_attributes):

        remote_nsa = self.topology.getNetwork(network).nsa
        return self.client.reserve(self.nsa_id, remote_nsa, connection_id, global_reservation_id, description, service_parameters, session_security_attributes)


    def cancelReservation(self, network, connection_id, session_security_attributes):

        remote_nsa = self.topology.getNetwork(network).nsa
        return self.client.cancelReservation(self.nsa_id, remote_nsa, connection_id, session_security_attributes)


    def provision(self, network, connection_id, session_security_attributes):

        remote_nsa = self.topology.getNetwork(network).nsa
        return self.client.provision(self.nsa_id, remote_nsa, connection_id, session_security_attributes)


    def releaseProvision(self, network, connection_id, session_security_attributes):

        remote_nsa = self.topology.getNetwork(network).nsa
        return self.client.releaseProvision(self.nsa_id, remote_nsa, connection_id, session_security_attributes)


    def query(self, network, query_filter, session_security_attributes):

        remote_nsa = self.topology.getNetwork(network).nsa
        return self.client.query(self.nsa_id, remote_nsa, query_filter, session_security_attributes)

