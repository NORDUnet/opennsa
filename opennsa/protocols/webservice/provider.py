import traceback

from twisted.python import log
from twisted.internet import defer

from opennsa import error



# Errors we shouldn't log about (handled elsewhere)
IGNORE_ERRORS = [ error.NoSuchConnectionError ]



def _createErrorMessage(err):
    error_type = err.value.__class__.__name__
    msg = err.getErrorMessage()
    tb = traceback.extract_tb( err.getTracebackObject() )
    if tb:
        filename, line, fun = tb[-1][0:3]
        error_message = '%s: %s (%s, line %s in %s)' % (error_type, msg, filename, line, fun)
    else:
        error_message = '%s: %s' % (error_type, msg)
    return error_message



class Provider:


    def __init__(self, nsi_service, requester_client):
        self.nsi_service = nsi_service
        self.requester_client = requester_client


    def reserve(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters):

        def notifyReserveSuccess(_):
            # should probably use result somehow
            d = self.requester_client.reserveConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, description, connection_id, service_parameters)
            return d

        def notifyReserveFailure(err):
            error_msg = _createErrorMessage(err)
            d = self.requester_client.reserveFailed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, 'TERMINATED', error_msg)
            if err.check(IGNORE_ERRORS):
                log.msg('Error during reservation call (failure has been send to client)')
                log.err(err)
            return d

        d = defer.maybeDeferred(self.nsi_service.reserve,
                                requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters)
        d.addCallbacks(notifyReserveSuccess, notifyReserveFailure)
        return d


    def provision(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, connection_id):

        def notifyProvisionSuccess(_):
            # should probably use result somehow
            global_reservation_id = None
            d = self.requester_client.provisionConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id)
            return d

        def notifyProvisionFailure(err):
            error_msg = _createErrorMessage(err)
            global_reservation_id = None
            d = self.requester_client.provisionFailed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, 'TERMINATED', error_msg)
            if err.check(IGNORE_ERRORS):
                log.msg('Error during provision call (failure has been send to client)')
                log.err(err)
            return d

        d = defer.maybeDeferred(self.nsi_service.provision, requester_nsa, provider_nsa, session_security_attr, connection_id)
        d.addCallbacks(notifyProvisionSuccess, notifyProvisionFailure)
        return d


    def release(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, connection_id):

        def notifyReleaseSuccess(_):
            # should probably use result somehow
            global_reservation_id = None
            d = self.requester_client.releaseConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id)
            return d

        def notifyReleaseFailure(err):
            error_msg = _createErrorMessage(err)
            global_reservation_id = None
            d = self.requester_client.releaseFailed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, 'TERMINATED', error_msg)
            if err.check(IGNORE_ERRORS):
                log.msg('Error during release call (failure has been send to client)')
                log.err(err)
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

        def notifyTerminateFailure(err):
            error_msg = _createErrorMessage(err)
            global_reservation_id = None
            d = self.requester_client.terminateFailed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, 'TERMINATED', error_msg)
            if err.check(IGNORE_ERRORS):
                log.msg('Error during release call (failure has been send to client)')
                log.err(err)
            return d

        d = self.nsi_service.terminate(requester_nsa, provider_nsa, session_security_attr, connection_id)
        d.addCallbacks(notifyTerminateSuccess, notifyTerminateFailure)
        return d


    def query(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, operation, connection_ids, global_reservation_ids):

        def notifyQuerySuccess(conns):
            d = self.requester_client.queryConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, operation, conns)
            return d

        def notifyQueryFailure(err):
            error_msg = _createErrorMessage(err)
            d = self.requester_client.queryFailed(reply_to, correlation_id, requester_nsa, provider_nsa, error_msg)
            if err.check(IGNORE_ERRORS):
                log.msg('Error during query call (failure has been send to client)')
                log.err(err)
            return d

        d = self.nsi_service.query(requester_nsa, provider_nsa, session_security_attr, operation, connection_ids, global_reservation_ids)
        d.addCallbacks(notifyQuerySuccess, notifyQueryFailure)
        return d

