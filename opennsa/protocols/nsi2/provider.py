from zope.interface import implementer

from twisted.python import log
from twisted.internet import defer, error

from opennsa.interface import INSIRequester


LOG_SYSTEM = 'nsi2.Provider'


RESERVE_RESPONSE        = 'reserve_response'
RESERVE_COMMIT_RESPONSE = 'reserve_commit_response'
RESERVE_ABORT_RESPONSE  = 'reserve_commit_response'
PROVISION_RESPONSE      = 'provision_response'
RELEASE_RESPONSE        = 'release_response'
TERMINATE_RESPONSE      = 'terminate_response'

QUERY_SUMMARY_RESPONSE  = 'query_summary_response'
QUERY_RECURSIVE_RESPONSE = 'query_recursive_response'



def logError(err, message_type):

    log.msg('Error during %s request: %s' % (message_type, err.getErrorMessage()), system=LOG_SYSTEM)
    if err.type not in [error.ConnectionRefusedError]: # occurs so often we don't want to look at it
        log.err(err, system=LOG_SYSTEM)



@implementer(INSIRequester)
class Provider:
    # This is part of the provider side of the protocol, and usually sits on top of the aggregator
    # As it sits on top of the aggregator - which is a provider - it implements the Requester interface
    # So it is Provider, that implements the Requester interface. If this doesn't confuse you, continue reading

    def __init__(self, service_provider, provider_client):

        self.service_provider = service_provider
        self.provider_client  = provider_client
        self.notifications = {}


    def reserve(self, nsi_header, connection_id, global_reservation_id, description, criteria, request_info):

        # we cannot create notification immediately, as there might not be a connection id yet
        # the notification mechanisms relies on the received ack coming before the confirmation, which is not ideal

        def setNotify(assigned_connection_id):
            if nsi_header.reply_to:
                self.notifications[(assigned_connection_id, RESERVE_RESPONSE)] = nsi_header
            return assigned_connection_id

        d = self.service_provider.reserve(nsi_header, connection_id, global_reservation_id, description, criteria, request_info)
        d.addCallback(setNotify)
        return d


    def reserveConfirmed(self, nsi_header, connection_id, global_reservation_id, description, service_parameters):
        try:
            nsi_header = self.notifications.pop( (connection_id, RESERVE_RESPONSE) )
            d = self.provider_client.reserveConfirmed(nsi_header, connection_id, global_reservation_id, description, service_parameters)
            d.addErrback(logError, 'reserveConfirmed')
            return d
        except KeyError:
            log.msg('No entity to notify about reserveConfirmed for %s' % connection_id, system=LOG_SYSTEM)
            return defer.succeed(None)


    def reserveFailed(self, nsi_header, connection_id, connection_states, err):
        try:
            nsi_header = self.notifications.pop( (connection_id, RESERVE_RESPONSE) )
            d = self.provider_client.reserveFailed(nsi_header, connection_id, connection_states, err)
            d.addErrback(logError, 'reserveFailed')
            return d
        except KeyError:
            log.msg('No entity to notify about reserveFailed for %s' % connection_id, system=LOG_SYSTEM)
            return defer.succeed(None)


    def reserveCommit(self, nsi_header, connection_id, request_info):

        if nsi_header.reply_to:
            self.notifications[(connection_id, RESERVE_COMMIT_RESPONSE)] = nsi_header
        return self.service_provider.reserveCommit(nsi_header, connection_id, request_info)


    def reserveCommitConfirmed(self, header, connection_id):

        try:
            org_header = self.notifications.pop( (connection_id, RESERVE_COMMIT_RESPONSE) )
            d = self.provider_client.reserveCommitConfirmed(org_header.reply_to, org_header.requester_nsa, org_header.provider_nsa, org_header.correlation_id, connection_id)
            d.addErrback(logError, 'reserveCommitConfirmed')
            return d
        except KeyError:
            log.msg('No entity to notify about reserveCommitConfirmed for %s' % connection_id, system=LOG_SYSTEM)
            return defer.succeed(None)


    def reserveAbort(self, header, connection_id, request_info):

        if header.reply_to:
            self.notifications[(connection_id, RESERVE_ABORT_RESPONSE)] = header
        return self.service_provider.reserveAbort(header, connection_id, request_info)


    def reserveAbortConfirmed(self, header, connection_id):

        try:
            org_header = self.notifications.pop( (connection_id, RESERVE_ABORT_RESPONSE) )
            d = self.provider_client.reserveAbortConfirmed(org_header.reply_to, org_header.requester_nsa, org_header.provider_nsa, org_header.correlation_id, connection_id)
            d.addErrback(logError, 'reserveAbortConfirmed')
            return d
        except KeyError:
            log.msg('No entity to notify about reserveAbortConfirmed for %s' % connection_id, system=LOG_SYSTEM)
            return defer.succeed(None)


    def provision(self, nsi_header, connection_id, request_info):

        if nsi_header.reply_to:
            self.notifications[(connection_id, PROVISION_RESPONSE)] = nsi_header
        return self.service_provider.provision(nsi_header, connection_id, request_info)


    def provisionConfirmed(self, header, connection_id):

        try:
            org_header = self.notifications.pop( (connection_id, PROVISION_RESPONSE) )
            d = self.provider_client.provisionConfirmed(org_header.reply_to, org_header.correlation_id, org_header.requester_nsa, org_header.provider_nsa, connection_id)
            d.addErrback(logError, 'provisionConfirmed')
            return d
        except KeyError:
            log.msg('No entity to notify about provisionConfirmed for %s' % connection_id, system=LOG_SYSTEM)
            return defer.succeed(None)


    def release(self, nsi_header, connection_id, request_info):

        if nsi_header.reply_to:
            self.notifications[(connection_id, RELEASE_RESPONSE)] = nsi_header
        return self.service_provider.release(nsi_header, connection_id, request_info)


    def releaseConfirmed(self, header, connection_id):

        try:
            org_header = self.notifications.pop( (connection_id, RELEASE_RESPONSE) )
            d = self.provider_client.releaseConfirmed(org_header.reply_to, org_header.correlation_id, org_header.requester_nsa, org_header.provider_nsa, connection_id)
            d.addErrback(logError, 'releaseConfirmed')
            return d
        except KeyError:
            log.msg('No entity to notify about releaseConfirmed for %s' % connection_id, system=LOG_SYSTEM)
            return defer.succeed(None)


    def terminate(self, nsi_header, connection_id, request_info):

        if nsi_header.reply_to:
            self.notifications[(connection_id, TERMINATE_RESPONSE)] = nsi_header
        return self.service_provider.terminate(nsi_header, connection_id, request_info)


    def terminateConfirmed(self, header, connection_id):

        try:
            org_header = self.notifications.pop( (connection_id, TERMINATE_RESPONSE) )
            return self.provider_client.terminateConfirmed(org_header.reply_to, org_header.correlation_id, org_header.requester_nsa, org_header.provider_nsa, connection_id)
        except KeyError:
            log.msg('No entity to notify about terminateConfirmed for %s' % connection_id, system=LOG_SYSTEM)
            return defer.succeed(None)

        d = self.service_provider.terminateConfirmed(header, connection_id)
        d.addErrback(logError, 'terminateConfirmed')
        return d

    # Query

    def querySummary(self, header, connection_ids, global_reservation_ids, request_info):

        if not header.reply_to:
            raise ValueError('Cannot perform querySummary request without a replyTo field in the header')
        if not header.correlation_id:
            raise ValueError('Cannot perform querySummary request without a correlationId field in the header')

        return self.service_provider.querySummary(header, connection_ids, global_reservation_ids)


    def querySummarySync(self, header, connection_ids, global_reservation_ids, request_info):

        if not header.reply_to:
            raise ValueError('Cannot perform querySummary request without a replyTo field in the header')
        if not header.correlation_id:
            raise ValueError('Cannot perform querySummary request without a correlationId field in the header')

        dc = defer.Deferred()
        self.notifications[(header.correlation_id, QUERY_SUMMARY_RESPONSE)] = dc

        # returns a deferred, but we don't use it (indicates message receival only), should it be chained?
        self.service_provider.querySummary(header, connection_ids, global_reservation_ids, request_info)
        return dc


    def querySummaryConfirmed(self, header, reservations):

        if header.reply_to is None:
            log.msg('No reply url to notify about query summary. Skipping notification.', system=LOG_SYSTEM)
            return defer.succeed(None)

        if (header.correlation_id, QUERY_SUMMARY_RESPONSE) in self.notifications:
            dc = self.notifications.pop((header.correlation_id, QUERY_SUMMARY_RESPONSE))
            dc.callback( reservations )
        else:
            return self.provider_client.querySummaryConfirmed(header.reply_to, header.requester_nsa, header.provider_nsa, header.correlation_id, reservations)


    def queryRecursive(self, header, connection_ids, global_reservation_ids, request_info):

        if not header.reply_to:
            raise ValueError('Cannot perform queryRecursive request without a replyTo field in the header')
        if not header.correlation_id:
            raise ValueError('Cannot perform queryRecursive request without a correlationId field in the header')

        return self.service_provider.queryRecursive(header, connection_ids, global_reservation_ids, request_info)


    def queryRecursiveConfirmed(self, header, reservations):

        if (header.correlation_id, QUERY_RECURSIVE_RESPONSE) in self.notifications:
            dc = self.notifications.pop( (header.correlation_id, QUERY_RECURSIVE_RESPONSE) )
            dc.callback( reservations )
        else:
            return self.provider_client.queryRecursiveConfirmed(header.reply_to, header.requester_nsa, header.provider_nsa, header.correlation_id, reservations)


    # requester interface

    def reserveTimeout(self, header, connection_id, notification_id, timestamp, timeout_value, originating_connection_id, originating_nsa):

        if header.reply_to is None:
            log.msg('No reply url to notify about reserve timeout. Skipping notification.', system=LOG_SYSTEM)
            return defer.succeed(None)

        d = self.provider_client.reserveTimeout(header.reply_to, header.requester_nsa, header.provider_nsa, header.correlation_id,
                                                connection_id, notification_id, timestamp, timeout_value, originating_connection_id, originating_nsa)
        d.addErrback(logError, 'reserveTimeout')
        return d


    def dataPlaneStateChange(self, header, connection_id, notification_id, timestamp, data_plane_status):

        if header.reply_to is None:
            log.msg('No reply url to notify about data plane state change. Skipping notification.', system=LOG_SYSTEM)
            return defer.succeed(None)

        active, version, consistent = data_plane_status
        d = self.provider_client.dataPlaneStateChange(header.reply_to, header.requester_nsa, header.provider_nsa, header.correlation_id,
                                                      connection_id, notification_id, timestamp, active, version, consistent)
        d.addErrback(logError, 'dataPlaneStateChange')
        return d


    def errorEvent(self, header, connection_id, notification_id, timestamp, event, info, service_ex):

        d = self.provider_client.errorEvent(header.reply_to, header.requester_nsa, header.provider_nsa, header.correlation_id,
                                            connection_id, notification_id, timestamp, event, info, service_ex)
        return d

