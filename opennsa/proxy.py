"""
Handy proxy wrapping for easier / shorter calls to NSI agents.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""



class NSIProxy:

    def __init__(self, client, nsa_):
        self.client     = client    # client adhering to the NSIInterface
        self.nsa_       = nsa_      # this is the identity of the caller


    def reserve(self, remote_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters):

        return self.client.reserve(self.nsa_, remote_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters)


    def terminate(self, remote_nsa, session_security_attr, connection_id):

        return self.client.terminate(self.nsa_, remote_nsa, session_security_attr, connection_id)


    def provision(self, remote_nsa, session_security_attr, connection_id):

        return self.client.provision(self.nsa_, remote_nsa, session_security_attr, connection_id)


    def release(self, remote_nsa, session_security_attr, connection_id):

        return self.client.release(self.nsa_, remote_nsa, session_security_attr, connection_id)


    def query(self, remote_nsa, session_security_attr, query_filter):

        return self.client.query(self.nsa_, remote_nsa, session_security_attr, query_filter)

