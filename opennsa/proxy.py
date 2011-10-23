"""
Handy proxy wrapping for easier / shorter calls to NSI agents.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""



class NSIProxy:

    def __init__(self, client, nsa_, topology):
        self.client     = client    # client adhering to the NSIInterface
        self.nsa_       = nsa_      # this is the identity of the caller
        self.topology   = topology  # used for network -> nsa lookups


    def reserve(self, network, session_security_attr, global_reservation_id, description, connection_id, service_parameters):

        remote_nsa = self.topology.getNetwork(network).nsa
        return self.client.reserve(self.nsa_, remote_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters)


    def reserveConfirmed(self, reply_to, remote_nsa, global_reservation_id, description, connection_id, service_parameters):

        return self.client.reserveConfirmed(reply_to, remote_nsa, self.nsa_, global_reservation_id, description, connection_id, service_parameters)


    def reserveFailed(self, remote_nsa, global_reservation_id, description, connection_id, service_exception):

        return self.clent.reserveFailed(remote_nsa, self.nsa_, global_reservation_id, description, connection_id, service_exception)


    def terminate(self, network, session_security_attr, connection_id):

        remote_nsa = self.topology.getNetwork(network).nsa
        return self.client.terminate(self.nsa_, remote_nsa, session_security_attr, connection_id)


    def provision(self, network, session_security_attr, connection_id):

        remote_nsa = self.topology.getNetwork(network).nsa
        return self.client.provision(self.nsa_, remote_nsa, session_security_attr, connection_id)


    def provisionConfirmed(self, reply_to, remote_nsa, global_reservation_id, connection_id):

        return self.client.provisionConfirmed(reply_to, remote_nsa, self.nsa_, global_reservation_id, connection_id)


    def release(self, network, session_security_attr, connection_id):

        remote_nsa = self.topology.getNetwork(network).nsa
        return self.client.release(self.nsa_, remote_nsa, session_security_attr, connection_id)


    def query(self, network, session_security_attributes, query_filter):

        remote_nsa = self.topology.getNetwork(network).nsa
        return self.client.query(self.nsa_, remote_nsa, session_security_attr, query_filter)

