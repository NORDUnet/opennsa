

from zope.interface import implements

from twisted.python import log
from twisted.internet import defer

from opennsa.interface import NSIInterface
from opennsa.protocols.webservice import client



class Requester:

    implements(NSIInterface)

    def __init__(self, provider_client):
        #self.nsi_service = nsi_service
        self.provider_client = provider_client

        self.calls = {}


    def addCall(self, provider_nsa, correlation_id, action, connection_id):

        key = (provider_nsa.uri(), correlation_id)
        assert key not in self.calls, 'Cannot have multiple calls with same NSA / correlationId'

        d = defer.Deferred()
        self.calls[key] = (action, connection_id, d)
        return d


    def triggerCall(self, provider_nsa, correlation_id, action, connection_id):

        #print "TRIGGER CALL", self.calls
        key = (provider_nsa.uri(), correlation_id)
        if not key in self.calls:
            print log.msg('Got callback for unknown call. Action: %s. NSA: %s' % (action, provider_nsa.uri()), system='opennsa.Requester')

        acd = self.calls.pop( (provider_nsa.uri(), correlation_id) )
        ract, rcid, d = acd
        assert ract == action and rcid == connection_id, "%s != %s and %s != %s" % (ract, action, rcid, connection_id)
        d.callback(connection_id)


    def reservation(self, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters):

        correlation_id = client.createCorrelationId()
        rd = self.addCall(provider_nsa, correlation_id, 'reservation', connection_id)
        cd = self.provider_client.reservation(correlation_id, requester_nsa, provider_nsa, session_security_attr,
                                              global_reservation_id, description, connection_id, service_parameters)
        # need to chain cd.errback to rd.errback (only error path)
        return rd


    def reservationConfirmed(self, correlation_id, requester_nsa, provider_nsa, session_security_attr,
                             global_reservation_id, description, connection_id, service_parameter):

        self.triggerCall(provider_nsa, correlation_id, 'reservation', connection_id)
#        #print "RES CONF", self.calls
#        acd = self.calls.pop( (provider_nsa.uri(), correlation_id) )
#        # CHECK!
#        action, rcid, d = acd
#        assert action == 'reservation' and rcid == connection_id
#        d.callback(connection_id)



    def provision(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        correlation_id = client.createCorrelationId()
        rd = self.addCall(provider_nsa, correlation_id, 'provision', connection_id)
        cd = self.provider_client.provision(correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id)
        # need to chain cd.errback to rd.errback (only error path)
        return rd


    def provisionConfirmed(self, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id):

        self.triggerCall(provider_nsa, correlation_id, 'provision', connection_id)
#        #print "RES CONF", self.calls
#        acd = self.calls.pop( (provider_nsa.uri(), correlation_id) )
#        # CHECK!
#        action, rcid, d = acd
#        assert action == 'provision' and rcid == connection_id
#        d.callback(connection_id)


    def release(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        correlation_id = client.createCorrelationId()
        rd = self.addCall(provider_nsa, correlation_id, 'release', connection_id)
        cd = self.provider_client.release(correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id)
        # need to chain cd.errback to rd.errback (only error path)
        return rd

    def releaseConfirmed(self, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id):

        self.triggerCall(provider_nsa, correlation_id, 'release', connection_id)


    def query(self, requester_nsa, provider_nsa, session_securit_attr, operation, connection_ids=None, global_reservation_ids=None):
        print "QUERY NOTHING"


