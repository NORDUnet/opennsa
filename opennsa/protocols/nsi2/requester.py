
import uuid
from zope.interface import implements

from twisted.python import log, failure
from twisted.internet import reactor, defer

from opennsa import error
from opennsa.interface import NSIInterface
#from opennsa.protocols.nsi2 import requesterclient



DEFAULT_CALLBACK_TIMEOUT = 60 # 1 minute
URN_UUID_PREFIX = 'urn:uuid:'


def createCorrelationId():
    return URN_UUID_PREFIX + str(uuid.uuid1())



class Requester:

    implements(NSIInterface)

    def __init__(self, requester_client, callback_timeout=DEFAULT_CALLBACK_TIMEOUT):

        self.requester_client = requester_client
        self.callback_timeout = callback_timeout
        self.calls = {}


    def addCall(self, provider_nsa, correlation_id, action):


        key = (provider_nsa.urn(), correlation_id)
        assert key not in self.calls, 'Cannot have multiple calls with same NSA / correlationId'

        d = defer.Deferred()
        call = reactor.callLater(self.callback_timeout, self.callbackTimeout, provider_nsa.urn(), correlation_id, action)
        self.calls[key] = (action, d, call)
        return d


    def callbackTimeout(self, provider_nsa, correlation_id, action):

        err = error.CallbackTimeoutError('Callback for call %s/%s from %s timed out.' % (correlation_id, action, provider_nsa))
        self.triggerCall(provider_nsa, correlation_id, action, err)


    def triggerCall(self, provider_nsa, correlation_id, action, result):

        assert provider_nsa.startswith('urn:'), 'Invalid provider nsa specified'
        #print "TRIGGER CALL", self.calls
        key = (provider_nsa, correlation_id)
        try:
            acd = self.calls.pop(key)
        except KeyError:
            log.msg('Got callback for unknown call. Action: %s. NSA: %s' % (action, provider_nsa), system='opennsa.Requester')
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


    def reserve(self, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters):

        correlation_id = createCorrelationId()

        def reserveRequestFailed(err):
            # invocation failed, so we error out immediately
            log.msg('Reserve invocation failed: %s' % err.getErrorMessage())
            self.triggerCall(provider_nsa.urn(), correlation_id, 'reserve', err.value)

        rd = self.addCall(provider_nsa, correlation_id, 'reserve')
        cd = self.requester_client.reserve(provider_nsa.endpoint,
                                           correlation_id, requester_nsa, provider_nsa, session_security_attr,
                                           global_reservation_id, description, connection_id, service_parameters)
        cd.addErrback(reserveRequestFailed)
        return rd


    def reserveConfirmed(self, correlation_id, requester_nsa, provider_nsa, session_security_attr,
                             global_reservation_id, description, connection_id, service_parameter):

        self.triggerCall(provider_nsa, correlation_id, 'reserve', connection_id)


    def reserveFailed(self, correlation_id, requester_nsa, provider_nsa, connection_id, session_security_attr, err):

        self.triggerCall(provider_nsa, correlation_id, 'reserve', err)


    def provision(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        correlation_id = createCorrelationId()

        def provisionRequestFailed(err):
            # invocation failed, so we error out immediately
            self.triggerCall(provider_nsa.urn(), correlation_id, 'provision', err.value)

        rd = self.addCall(provider_nsa, correlation_id, 'provision')
        cd = self.requester_client.provision(correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id)
        cd.addErrback(provisionRequestFailed)
        return rd


    def provisionConfirmed(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id):

        self.triggerCall(provider_nsa, correlation_id, 'provision', connection_id)


    def provisionFailed(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id, err):

        self.triggerCall(provider_nsa, correlation_id, 'provision', err)


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


    def query(self, requester_nsa, provider_nsa, session_security_attr, operation='Summary', connection_ids=None, global_reservation_ids=None):

        correlation_id = createCorrelationId()

        def queryRequestFailed(err):
            # invocation failed, so we error out immediately
            self.triggerCall(provider_nsa.urn(), correlation_id, 'query', err.value)

        rd = self.addCall(provider_nsa, correlation_id, 'query')
        cd = self.requester_client.query(correlation_id, requester_nsa, provider_nsa, session_security_attr, operation, connection_ids, global_reservation_ids)
        cd.addErrback(queryRequestFailed)
        return rd

    def queryConfirmed(self, correlation_id, requester_nsa, provider_nsa, query_result):

        self.triggerCall(provider_nsa, correlation_id, 'query', query_result)


    def queryFailed(self, correlation_id, requester_nsa, provider_nsa, error_message):

        self.triggerCall(provider_nsa, correlation_id, 'query', error.QueryError(error_message))

