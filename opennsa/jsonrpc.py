"""
Implementation of JSON-RPC via netstrings for Twisted.

See http://json-rpc.org/ for specificiation

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import json
import uuid

from zope.interface import implements

from twisted.python import log
from twisted.internet import reactor, protocol, endpoints, defer
from twisted.protocols.basic import NetstringReceiver

from opennsa.interface import NSIInterface



class JSONRPCError(Exception):

    def __init__(self, message):
        self.message = message


    def __str__(self):
        return '<JSONRPCError:%s>' % self.message



class NoSuchMethodError(JSONRPCError):
    pass



NOSUCHMETHOD = '_NOSUCHMETHOD'

EXCEPTIONS = {
    NOSUCHMETHOD : NoSuchMethodError
}


class ServiceProxy(NetstringReceiver):

    def connectionMade(self):
        self.rpc_ids = {}
        self.rpc_timeouts = {}


    def call(self, method_name, *args):
        rpc_id = uuid.uuid1().hex
        data = json.dumps( {"method": method_name, 'params': args, 'id': rpc_id} )
        d = defer.Deferred()

        self.sendString(data)
        self.registerCallID(rpc_id, d)
        return d


    def registerCallID(self, rpc_id, d):
        assert rpc_id not in self.rpc_ids
        self.rpc_ids[rpc_id] = d
        # need to schedule timeout


    def stringReceived(self, string):
        try:
            response = json.loads(string)
            rpc_id = response['id']
        except ValueError, e:
            return log.err('Error parsing incoming JSON payload')
        except KeyError, e:
            return log.err('No id in message')

        d = self.rpc_ids.pop(rpc_id, None)
        if d is None:
            return log.err('Unknown RPC id in message (%s)' % rpc_id)

        if 'error' in response:
            e = EXCEPTIONS.get(response['error'], JSONRPCError)
            d.errback(e(response['error']))
        elif 'result' in response:
            d.callback(response['result'])
        else:
            d.errback('Invalid message response (neither error or result in payload)')


    def connectionLost(self, reason):
        # trigger all timeouts
        pass



class JSONRPCService(NetstringReceiver):

    def connectionMade(self):
        self.rpc_ids = {}
        self.rpc_timeouts = {}

    def __init__(self):
        self.functions = {}


    def registerFunction(self, name, func):
        self.functions[name] = func


    def errorReply(self, rpc_id, error_msg):

        message = json.dumps( { 'id': rpc_id, 'error': error_msg } )
        self.sendString(message)

    def reply(self, rpc_id, result):

        message = json.dumps( { 'id': rpc_id, 'result': result } )
        self.sendString(message)


    def stringReceived(self, string):

        try:
            request = json.loads(string)
            rpc_id = request['id']
        except ValueError, e:
            log.msg('Error parsing JSON RPC payload (invalid JSON)')
        except KeyError, e:
            log.msg('No RPC id in JSON RPC message')

        try:
            method_name = request['method']
            method_args = request['params']
        except KeyError, e:
            log.msg('Missing method information, cannot dispatch')
            return self.errorReply(rpc_id, 'Missing method information')

        try:
            f = self.functions[method_name]
        except KeyError:
            #return self.errorReply(rpc_id, 'No such method (%s)' % method_name)
            return self.errorReply(rpc_id, NOSUCHMETHOD)

        try:
            result = f(*method_args)
            if isinstance(result, defer.Deferred):
                result.addCallbacks(lambda r : self.reply(rpc_id, r),
                                    lambda f : self.errorReply(rpc_id, str(f)))
                # FIXME handle serialization fail in reply callback
            else:
                # FIXME handle serialization fail
                self.reply(rpc_id, result)
        except Exception, e:
            return self.errorReply(rpc_id, str(e))




class JSONRPCClient:

    implements(NSIInterface)

    def __init__(self):
        self.factory = protocol.Factory()
        self.factory.protocol = ServiceProxy


    def _getProxy(self, nsa):
        host, port = nsa.getHostPort()
        point = endpoints.TCP4ClientEndpoint(reactor, host, port)
        d = point.connect(self.factory)
        return d


    def _issueProxyCall(self, nsa, func):
        d = self._getProxy(nsa)
        d.addCallback(nsa)
        return d


    def reserve(self, requester_nsa, provider_nsa, reservation_id, description, connection_id,
                service_parameters, session_security_attributes):

        def gotProxy(proxy):
            return proxy.call('Reserve', requester_nsa, provider_nsa, reservation_id, description, connection_id, service_parameters, session_security_attributes)

        return self._issueProxyCall(provider_nsa, gotProxy)


    def cancelReservation(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        def gotProxy(proxy):
            return proxy.call('CancelReservation', requester_nsa, provider_nsa, connection_id, session_security_attributes)

        return self._issueProxyCall(provider_nsa, gotProxy)


    def provision(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        def gotProxy(proxy):
            return proxy.call('Provision', requester_nsa, provider_nsa, connection_id, session_security_attributes)

        return self._issueProxyCall(provider_nsa, gotProxy)


    def releaseProvision(self, requester_nsa, provider_nsa, connection_id, session_security_attributes):

        def gotProxy(proxy):
            return proxy.call('ReleaseProvision', requester_nsa, provider_nsa, connection_id, session_security_attributes)

        return self._issueProxyCall(provider_nsa, gotProxy)


    def query(self, requester_nsa, provider_nsa, session_security_attributes):

        raise NotImplementedError('Query, nahh..')



class JSONRPCNSIServiceAdaptor:

    def __init__(self, jsonrpc_service, nsi_service):

        jsonrpc_service.registerFunction('Reserve',             nsi_service.reserve)
        jsonrpc_service.registerFunction('CancelReservation',   nsi_service.cancelReservation)
        jsonrpc_service.registerFunction('Provision',           nsi_service.provision)
        jsonrpc_service.registerFunction('ReleaseProvision',    nsi_service.releaseProvision)
        jsonrpc_service.registerFunction('Query',               nsi_service.query)

