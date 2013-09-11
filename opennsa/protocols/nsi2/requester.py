
import uuid
from zope.interface import implements

from twisted.python import log, failure
from twisted.internet import reactor, defer

from opennsa import error
from opennsa.interface import INSIProvider


LOG_SYSTEM = 'nsi2.Requester'

DEFAULT_CALLBACK_TIMEOUT = 60 # 1 minute
URN_UUID_PREFIX = 'urn:uuid:'

RESERVE         = 'reserve'
RESERVE_COMMIT  = 'reserve_commit'
PROVISION       = 'provision'
RELEASE         = 'release'
TERMINATE       = 'terminate'



def createCorrelationId():
    return URN_UUID_PREFIX + str(uuid.uuid1())



class Requester:

    # In OpenNSA the requester is something that acts as a provider :-)
    implements(INSIProvider)

    def __init__(self, requester_client, callback_timeout=None):

        self.requester_client = requester_client

        self.callback_timeout = callback_timeout or DEFAULT_CALLBACK_TIMEOUT
        self.calls = {}
        self.notifications = defer.DeferredQueue()


    def addCall(self, provider_nsa, correlation_id, action):

        key = (provider_nsa, correlation_id)
        assert key not in self.calls, 'Cannot have multiple calls with same NSA / correlationId'

        d = defer.Deferred()
        call = reactor.callLater(self.callback_timeout, self.callbackTimeout, provider_nsa, correlation_id, action)
        self.calls[key] = (action, d, call)
        return d


    def callbackTimeout(self, provider_nsa, correlation_id, action):

        err = error.CallbackTimeoutError('Callback for call %s/%s from %s timed out.' % (correlation_id, action, provider_nsa))
        self.triggerCall(provider_nsa, correlation_id, action, err)


    def triggerCall(self, provider_nsa, correlation_id, action, result):

        key = (provider_nsa, correlation_id)
        try:
            acd = self.calls.pop(key)
        except KeyError:
            log.msg('Got callback for unknown call. Action: %s. NSA: %s' % (action, provider_nsa), system=LOG_SYSTEM)
            return

        ract, d, call = acd
        assert ract == action, "Mismatching actions for corrolation id %s. Expected: %s. Received: %s" % (correlation_id, ract, action)

        # cancel the timeout call if it is still scheduled
        if call.active():
            call.cancel()

        if isinstance(result, BaseException) or isinstance(result, failure.Failure):
            d.errback(result)
        else:
            d.callback(result)


    def reserve(self, header, connection_id, global_reservation_id, description, service_parameters):

        if header.correlation_id is not None:
            log.msg('Reserve ignoring specified correlation id')
        if header.reply_to is not None:
            log.msg('Reserve ignoring reply to')

        header.correlation_id = createCorrelationId()

        def reserveRequestFailed(err):
            # invocation failed, so we error out immediately
            log.msg('Reserve invocation failed: %s' % err.getErrorMessage(), system=LOG_SYSTEM)
            self.triggerCall(header.provider_nsa, header.correlation_id, RESERVE, err.value)

        rd = self.addCall(header.provider_nsa, header.correlation_id, RESERVE)
        cd = self.requester_client.reserve(header, connection_id, global_reservation_id, description, service_parameters)
        cd.addErrback(reserveRequestFailed)
        return rd


    def reserveConfirmed(self, header, connection_id, global_reservation_id, description, service_parameter):

        self.triggerCall(header.provider_nsa, header.correlation_id, RESERVE, connection_id)


    def reserveFailed(self, correlation_id, requester_nsa, provider_nsa, connection_id, session_security_attr, err):

        self.triggerCall(provider_nsa, correlation_id, RESERVE, err)


    def reserveCommit(self, header, connection_id):

        header.correlation_id = createCorrelationId()

        def reserveCommitFailed(err):
            # invocation failed, so we error out immediately
            log.msg('ReserveCommit invocation failed: %s' % err.getErrorMessage())
            self.triggerCall(header.provider_nsa, header.correlation_id, RESERVE_COMMIT, err.value)

        rd = self.addCall(header.provider_nsa, header.correlation_id, RESERVE_COMMIT)
        cd = self.requester_client.reserveCommit(header, connection_id)
        cd.addErrback(reserveCommitFailed)
        return rd


    def reserveCommitConfirmed(self, header, connection_id):

        self.triggerCall(header.provider_nsa, header.correlation_id, RESERVE_COMMIT, connection_id)


    def provision(self, header, connection_id):

        header.correlation_id = createCorrelationId()

        def provisionRequestFailed(err):
            # invocation failed, so we error out immediately
            self.triggerCall(header.provider_nsa, header.correlation_id, PROVISION, err.value)

        rd = self.addCall(header.provider_nsa, header.correlation_id, PROVISION)
        cd = self.requester_client.provision(header, connection_id)
        cd.addErrback(provisionRequestFailed)
        return rd


    def provisionConfirmed(self, header, connection_id):

        self.triggerCall(header.provider_nsa, header.correlation_id, PROVISION, connection_id)


    def provisionFailed(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id, err):

        self.triggerCall(provider_nsa, correlation_id, PROVISION, err)


    def release(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        correlation_id = createCorrelationId()

        def releaseRequestFailed(err):
            # invocation failed, so we error out immediately
            self.triggerCall(provider_nsa.urn(), correlation_id, 'release', err.value)

        rd = self.addCall(provider_nsa, correlation_id, 'release')
        cd = self.requester_client.release(correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id)
        cd.addErrback(releaseRequestFailed)
        return rd

    def releaseConfirmed(self, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id):

        self.triggerCall(provider_nsa, correlation_id, 'release', connection_id)


    def releaseFailed(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id, err):

        self.triggerCall(provider_nsa, correlation_id, 'release', err)


    def terminate(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        correlation_id = createCorrelationId()

        def terminateRequestFailed(err):
            # invocation failed, so we error out immediately
            self.triggerCall(provider_nsa.urn(), correlation_id, 'terminate', err.value)

        rd = self.addCall(provider_nsa, correlation_id, 'terminate')
        cd = self.requester_client.terminate(correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id)
        cd.addErrback(terminateRequestFailed)
        return rd


    def terminateConfirmed(self, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id):

        self.triggerCall(provider_nsa, correlation_id, 'terminate', connection_id)


    def terminateFailed(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id, err):

        self.triggerCall(provider_nsa, correlation_id, 'terminate', err)


    def querySummary(self, header, connection_ids=None, global_reservation_ids=None):

        # we just use sync for this, keep it simple
        d = self.requester_client.querySummarySync(header, connection_ids, global_reservation_ids)
        return d


    def queryConfirmed(self, correlation_id, requester_nsa, provider_nsa, query_result):

        self.triggerCall(provider_nsa, correlation_id, 'query', query_result)


    def queryFailed(self, correlation_id, requester_nsa, provider_nsa, error_message):

        self.triggerCall(provider_nsa, correlation_id, 'query', error.QueryError(error_message))


    def errorEvent(self, header, connection_id, notification_id, timestamp, event, info, service_ex):

        data = (connection_id, notification_id, timestamp, event, info, service_ex)
        return self.notifications.put( ('errorEvent', header, data) )


    def dataPlaneStateChange(self, header, connection_id, notification_id, timestamp, data_plane_status):

        data = (connection_id, notification_id, timestamp, data_plane_status)
        return self.notifications.put( ('dataPlaneStateChange', header, data) )


    def reserveTimeout(self, header, connection_id, notification_id, timestamp, timeout_value, org_connection_id, org_nsa):

        data = (connection_id, notification_id, timestamp, timeout_value, org_connection_id, org_nsa)
        return self.notifications.put( ('reserveTimeout', header, data) )

