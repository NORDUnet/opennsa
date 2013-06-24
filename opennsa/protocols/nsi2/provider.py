import traceback

from twisted.python import log
from twisted.internet import defer


WS_PROTO_EVENT_SYSTEM = 'nsi-2.0-soap'

LOG_SYSTEM = 'protocol.nsi2soap'


RESERVE_RESPONSE        = 'reserve_response'
RESERVE_COMMIT_RESPONSE = 'reserve_commit_response'



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

    # needs more implements

    def __init__(self, service_provider, provider_client):

        self.service_provider = service_provider
        self.provider_client  = provider_client
        self.notifications = {}


    def reserve(self, nsi_header, connection_id, global_reservation_id, description, service_parameters):

        # we cannot create notification immediately, as there might not be a connection id yet
        # the notification mechanisms relies on the received ack coming before the confirmation, which is not ideal

        def setNotify(assigned_connection_id):
            if nsi_header.reply_to:
                self.notifications[(assigned_connection_id, RESERVE_RESPONSE)] = nsi_header
            return assigned_connection_id

        d = self.service_provider.reserve(nsi_header, connection_id, global_reservation_id, description, service_parameters)
        d.addCallback(setNotify)
        return d


    def reserveConfirmed(self, nsi_header, connection_id, global_reservation_id, description, service_parameters):
        try:
            nsi_header = self.notifications.pop( (connection_id, RESERVE_RESPONSE) )
            return self.provider_client.reserveConfirmed(nsi_header, connection_id, global_reservation_id, description, service_parameters)
        except KeyError, e:
            log.msg('No entity to notify about reserveConfirmed', log_system=LOG_SYSTEM)
            return defer.succeed(None)


    def reserveCommit(self, nsi_header, connection_id):

        if nsi_header.reply_to:
            self.notifications[(connection_id, RESERVE_COMMIT_RESPONSE)] = nsi_header
        return self.service_provider.reserveCommit(nsi_header, connection_id)


    def reserveCommitConfirmed(self, header, connection_id):

        try:
            org_header = self.notifications.pop( (connection_id, RESERVE_COMMIT_RESPONSE) )
            return self.provider_client.reserveCommitConfirmed(org_header.reply_to, org_header.requester_nsa, org_header.provider_nsa, org_header.correlation_id, connection_id)
        except KeyError, e:
            log.msg('No entity to notify about reserveConfirmed', log_system=LOG_SYSTEM)
            return defer.succeed(None)


    def reserveTimeout(self, nsi_header, connection_id, notification_id, timestamp, timeout_value, originating_connection_id, originating_nsa):

        print "No reserve timeout implemented in nsi2 soap provider yet"


    def provision(self, nsi_header, connection_id):

        return self.service_provider(nsi_header, connection_id)


    def release(self, nsi_header, connection_id):

        return self.service_provider(nsi_header, connection_id)


    def terminate(self, nsi_header, connection_id):

        return self.service_provider(nsi_header, connection_id)


    # Need to think about how to do sync / async query

    def querySummary(self, nsi_header, connection_ids, global_reservation_ids):

        return self.service_provider(nsi_header, connection_ids, global_reservation_ids)


