





class Provider:


    def __init__(self, nsi_service, requester_client):
        self.nsi_service = nsi_service
        self.requester_client = requester_client


    def reservation(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters):

        def notifyReservationSuccess(_):
            # should probably use result somehow
            d = self.requester_client.reservationConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, description, connection_id, service_parameters)
            return d

        print "PROVIDER RESERVATION"
        d = self.nsi_service.reservation(requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters)
        d.addCallback(notifyReservationSuccess)
        return d



    def provision(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, connection_id):

        def notifyProvisionSuccess(_):
            # should probably use result somehow
            global_reservation_id = None
            d = self.requester_client.provisionConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id)
            return d

        print "PROVIDER PROVISION"
        d = self.nsi_service.provision(requester_nsa, provider_nsa, session_security_attr, connection_id)
        d.addCallback(notifyProvisionSuccess)
        return d


    def release(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, connection_id):

        def notifyReleaseSuccess(_):
            # should probably use result somehow
            global_reservation_id = None
            d = self.requester_client.releaseConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id)
            return d

        print "PROVIDER RELEASE"
        d = self.nsi_service.release(requester_nsa, provider_nsa, session_security_attr, connection_id)
        d.addCallback(notifyReleaseSuccess)
        return d


    def terminate(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, connection_id):

        def notifyTerminateSuccess(_):
            # should probably use result somehow
            global_reservation_id = None
            d = self.requester_client.terminateConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id)
            return d

        print "PROVIDER TERMINATE"
        d = self.nsi_service.terminate(requester_nsa, provider_nsa, session_security_attr, connection_id)
        d.addCallback(notifyTerminateSuccess)
        return d


