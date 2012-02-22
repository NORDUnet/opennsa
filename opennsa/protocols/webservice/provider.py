import traceback

from twisted.python import log
from twisted.internet import defer

from opennsa import error, registry, subscription


WS_PROTO_EVENT_SYSTEM = 'nsi-1.0-soap'


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


    def __init__(self, event_registry, requester_client):
        self.requester_client = requester_client
        self.event_registry = event_registry

        event_registry.registerEventHandler(registry.RESERVE_RESPONSE,   self.notifyReserveResult,   WS_PROTO_EVENT_SYSTEM)
        event_registry.registerEventHandler(registry.PROVISION_RESPONSE, self.notifyProvisionResult, WS_PROTO_EVENT_SYSTEM)
        event_registry.registerEventHandler(registry.RELEASE_RESPONSE,   self.notifyReleaseResult,   WS_PROTO_EVENT_SYSTEM)
        event_registry.registerEventHandler(registry.TERMINATE_RESPONSE, self.notifyTerminateResult, WS_PROTO_EVENT_SYSTEM)
        event_registry.registerEventHandler(registry.QUERY_RESPONSE,     self.notifyQueryResult,     WS_PROTO_EVENT_SYSTEM)


    def _extractData(self, data):

        reply_to                = data['reply_to']
        correlation_id          = data['correlation_id']
        requester_nsa           = data['requester_nsa']
        provider_nsa            = data['provider_nsa']
        connection_id           = data['connection_id']
        global_reservation_id   = data['global_reservation_id']

        return reply_to, correlation_id, requester_nsa, provider_nsa, connection_id, global_reservation_id


    def reserve(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters):

        data = { 'reply_to'      : reply_to,      'correlation_id'        : correlation_id,
                 'requester_nsa' : requester_nsa, 'provider_nsa'          : provider_nsa,
                 'connection_id' : connection_id, 'global_reservation_id' : None,
                 'description'   : description,   'service_parameters'    : service_parameters }

        sub = subscription.Subscription(registry.RESERVE_RESPONSE, WS_PROTO_EVENT_SYSTEM, data)

        handler = self.event_registry.getHandler(registry.RESERVE, registry.SYSTEM_SERVICE)
        d = defer.maybeDeferred(handler, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters, sub)
        return d


    def notifyReserveResult(self, success, result, data):

        reply_to, correlation_id, requester_nsa, provider_nsa, connection_id, global_reservation_id = self._extractData(data)
        description         = data['description']
        service_parameters  = data['service_parameters']

        if success:
            d = self.requester_client.reserveConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, description, connection_id, service_parameters)
            return d
        else:
            error_msg = _createErrorMessage(result)
            d = self.requester_client.reserveFailed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, 'TERMINATED', error_msg)
            return d


    def provision(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, connection_id):

        data = { 'reply_to'      : reply_to,      'correlation_id'        : correlation_id,
                 'requester_nsa' : requester_nsa, 'provider_nsa'          : provider_nsa,
                 'connection_id' : connection_id, 'global_reservation_id' : None }
        sub = subscription.Subscription(registry.PROVISION_RESPONSE, WS_PROTO_EVENT_SYSTEM, data)

        handler = self.event_registry.getHandler(registry.PROVISION, registry.SYSTEM_SERVICE)
        d = defer.maybeDeferred(handler, requester_nsa, provider_nsa, session_security_attr, connection_id, sub)
        return d


    def notifyProvisionResult(self, success, result, data):

        reply_to, correlation_id, requester_nsa, provider_nsa, connection_id, global_reservation_id = self._extractData(data)

        if success:
            d = self.requester_client.provisionConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id)
            return d
        else:
            error_msg = _createErrorMessage(result)
            d = self.requester_client.provisionFailed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, 'TERMINATED', error_msg)
            return d


    def release(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, connection_id):

        data = { 'reply_to'      : reply_to,      'correlation_id'        : correlation_id,
                 'requester_nsa' : requester_nsa, 'provider_nsa'          : provider_nsa,
                 'connection_id' : connection_id, 'global_reservation_id' : None }
        sub = subscription.Subscription(registry.RELEASE_RESPONSE, WS_PROTO_EVENT_SYSTEM, data)

        handler = self.event_registry.getHandler(registry.RELEASE, registry.SYSTEM_SERVICE)
        d = defer.maybeDeferred(handler, requester_nsa, provider_nsa, session_security_attr, connection_id, sub)
        return d


    def notifyReleaseResult(self, success, result, data):

        reply_to, correlation_id, requester_nsa, provider_nsa, connection_id, global_reservation_id = self._extractData(data)

        if success:
            d = self.requester_client.releaseConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id)
            return d
        else:
            error_msg = _createErrorMessage(result)
            d = self.requester_client.releaseFailed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, 'TERMINATED', error_msg)
            return d


    def terminate(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, connection_id):

        data = { 'reply_to'      : reply_to,      'correlation_id'        : correlation_id,
                 'requester_nsa' : requester_nsa, 'provider_nsa'          : provider_nsa,
                 'connection_id' : connection_id, 'global_reservation_id' : None }
        sub = subscription.Subscription(registry.TERMINATE_RESPONSE, WS_PROTO_EVENT_SYSTEM, data)

        handler = self.event_registry.getHandler(registry.TERMINATE, registry.SYSTEM_SERVICE)
        d = defer.maybeDeferred(handler, requester_nsa, provider_nsa, session_security_attr, connection_id, sub)
        return d


    def notifyTerminateResult(self, success, result, data):

        reply_to, correlation_id, requester_nsa, provider_nsa, connection_id, global_reservation_id = self._extractData(data)

        if success:
            d = self.requester_client.terminateConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id)
            return d
        else:
            error_msg = _createErrorMessage(result)
            d = self.requester_client.terminateFailed(reply_to, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, 'TERMINATED', error_msg)
            return d


    def query(self, correlation_id, reply_to, requester_nsa, provider_nsa, session_security_attr, operation, connection_ids, global_reservation_ids):

        data = { 'reply_to'      : reply_to,      'correlation_id'        : correlation_id,
                 'requester_nsa' : requester_nsa, 'provider_nsa'          : provider_nsa,
                 'operation'     : operation,     'connection_ids'        : connection_ids,
                 'global_reservation_ids' : global_reservation_ids }

        sub = subscription.Subscription(registry.QUERY_RESPONSE, WS_PROTO_EVENT_SYSTEM, data)

        handler = self.event_registry.getHandler(registry.QUERY, registry.SYSTEM_SERVICE)
        d = defer.maybeDeferred(handler, requester_nsa, provider_nsa, session_security_attr, operation, connection_ids, global_reservation_ids, sub)
        return d


    def notifyQueryResult(self, success, result, data):

        reply_to                = data['reply_to']
        correlation_id          = data['correlation_id']
        requester_nsa           = data['requester_nsa']
        provider_nsa            = data['provider_nsa']
        operation               = data['operation']

        if success:
            d = self.requester_client.queryConfirmed(reply_to, correlation_id, requester_nsa, provider_nsa, operation, result)
            return d
        else:
            error_msg = _createErrorMessage(result)
            d = self.requester_client.queryFailed(reply_to, correlation_id, requester_nsa, provider_nsa, error_msg)
            return d

