

from zope.interface import implements

from twisted.python import log, failure
from twisted.internet import reactor, defer

from opennsa import error
from opennsa.interface import NSIInterface
from opennsa.protocols.webservice import client



DEFAULT_CALLBACK_TIMEOUT = 60 # 1 minute



class Requester:

    implements(NSIInterface)

    def __init__(self, provider_client, callback_timeout=DEFAULT_CALLBACK_TIMEOUT):

        self.provider_client = provider_client
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
        assert ract == action, "%s != %s" % (ract, action)

        # cancel the timeout call if it is still scheduled
        if call.active():
            call.cancel()

        if isinstance(result, BaseException) or isinstance(result, failure.Failure):
            d.errback(result)
        else:
            d.callback(result)


    def reserve(self, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters):

        correlation_id = client.createCorrelationId()

        def reserveRequestFailed(err):
            # invocation failed, so we error out immediately
            self.triggerCall(provider_nsa.urn(), correlation_id, 'reserve', error.ReserveError(err.getErrorMessage()))

        rd = self.addCall(provider_nsa, correlation_id, 'reserve')
        cd = self.provider_client.reserve(correlation_id, requester_nsa, provider_nsa, session_security_attr,
                                          global_reservation_id, description, connection_id, service_parameters)
        cd.addErrback(reserveRequestFailed)
        return rd


    def reserveConfirmed(self, correlation_id, requester_nsa, provider_nsa, session_security_attr,
                             global_reservation_id, description, connection_id, service_parameter):

        self.triggerCall(provider_nsa, correlation_id, 'reserve', connection_id)


    def reserveFailed(self, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_message):

        self.triggerCall(provider_nsa, correlation_id, 'reserve', error.ReserveError(error_message))


    def provision(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        correlation_id = client.createCorrelationId()

        def provisionRequestFailed(err):
            # invocation failed, so we error out immediately
            self.triggerCall(provider_nsa.urn(), correlation_id, 'provision', error.ProvisionError(err.getErrorMessage()))

        rd = self.addCall(provider_nsa, correlation_id, 'provision')
        cd = self.provider_client.provision(correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id)
        cd.addErrback(provisionRequestFailed)
        return rd


    def provisionConfirmed(self, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id):

        self.triggerCall(provider_nsa, correlation_id, 'provision', connection_id)


    def provisionFailed(self, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_message):

        self.triggerCall(provider_nsa, correlation_id, 'provision', error.ProvisionError(error_message))


    def release(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        correlation_id = client.createCorrelationId()

        def releaseRequestFailed(err):
            # invocation failed, so we error out immediately
            self.triggerCall(provider_nsa.urn(), correlation_id, 'release', error.ReleaseError(err.getErrorMessage()))

        rd = self.addCall(provider_nsa, correlation_id, 'release')
        cd = self.provider_client.release(correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id)
        cd.addErrback(releaseRequestFailed)
        return rd

    def releaseConfirmed(self, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id):

        self.triggerCall(provider_nsa, correlation_id, 'release', connection_id)


    def releaseFailed(self, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_message):

        self.triggerCall(provider_nsa, correlation_id, 'release', error.ReleaseError(error_message))


    def terminate(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        correlation_id = client.createCorrelationId()

        def terminateRequestFailed(err):
            # invocation failed, so we error out immediately
            self.triggerCall(provider_nsa.urn(), correlation_id, 'terminate', error.TerminateError(err.getErrorMessage()))

        rd = self.addCall(provider_nsa, correlation_id, 'terminate')
        cd = self.provider_client.terminate(correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id)
        cd.addErrback(terminateRequestFailed)
        return rd


    def terminateConfirmed(self, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id):

        self.triggerCall(provider_nsa, correlation_id, 'terminate', connection_id)


    def terminateFailed(self, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_message):

        self.triggerCall(provider_nsa, correlation_id, 'terminate', error.TerminateError(error_message))


    def query(self, requester_nsa, provider_nsa, session_security_attr, operation='Summary', connection_ids=None, global_reservation_ids=None):

        correlation_id = client.createCorrelationId()

        def queryRequestFailed(err):
            # invocation failed, so we error out immediately
            self.triggerCall(provider_nsa.urn(), correlation_id, 'query', error.QueryError(err.getErrorMessage()))

        rd = self.addCall(provider_nsa, correlation_id, 'query')
        cd = self.provider_client.query(correlation_id, requester_nsa, provider_nsa, session_security_attr, operation, connection_ids, global_reservation_ids)
        cd.addErrback(queryRequestFailed)
        return rd

    def queryConfirmed(self, correlation_id, requester_nsa, provider_nsa, query_result):

        self.triggerCall(provider_nsa, correlation_id, 'query', query_result)


    def queryFailed(self, correlation_id, requester_nsa, provider_nsa, error_message):

        self.triggerCall(provider_nsa, correlation_id, 'query', error.QueryError(error_message))

