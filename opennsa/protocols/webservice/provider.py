


class Provider:


    def __init__(self, nsi_service, requester_client):
        self.nsi_service = nsi_service
        self.requester_client = requester_client


    def reservation(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters):

        def notifyReservationSuccess(_):
            # should probably use result somehow
            d = self.requester_client.reservationConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, description, connection_id, service_parameters)
            return d

        def notifyReservationFailure(err):
            error_msg = err.getErrorMessage()
            d = self.requester_client.reservationFailed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, 'TERMINATED', error_msg)
            return d

        d = self.nsi_service.reservation(requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters)
        d.addCallbacks(notifyReservationSuccess, notifyReservationFailure)
        return d


    def provision(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, connection_id):

        def notifyProvisionSuccess(_):
            # should probably use result somehow
            global_reservation_id = None
            d = self.requester_client.provisionConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id)
            return d

        d = self.nsi_service.provision(requester_nsa, provider_nsa, session_security_attr, connection_id)
        d.addCallback(notifyProvisionSuccess)
        return d


    def release(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, connection_id):

        def notifyReleaseSuccess(_):
            # should probably use result somehow
            global_reservation_id = None
            d = self.requester_client.releaseConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id)
            return d

        def notifyReleaseFailure(err):
            error_msg = err.getErrorMessage()
            global_reservation_id = None
            d = self.requester_client.releaseFailed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, 'TERMINATED', error_msg)
            return d

        d = self.nsi_service.release(requester_nsa, provider_nsa, session_security_attr, connection_id)
        d.addCallbacks(notifyReleaseSuccess, notifyReleaseFailure)
        return d


    def terminate(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, connection_id):

        def notifyTerminateSuccess(_):
            # should probably use result somehow
            global_reservation_id = None
            d = self.requester_client.terminateConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id)
            return d

        d = self.nsi_service.terminate(requester_nsa, provider_nsa, session_security_attr, connection_id)
        d.addCallback(notifyTerminateSuccess)
        return d


    def query(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, operation, connection_ids, global_reservation_ids):

        def notifyQuerySuccess(conns):
            d = self.requester_client.queryConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, operation, conns)
            return d

        d = self.nsi_service.query(requester_nsa, provider_nsa, session_security_attr, operation, connection_ids, global_reservation_ids)
        d.addCallback(notifyQuerySuccess)
        return d


