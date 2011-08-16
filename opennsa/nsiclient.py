"""
OpenNSA NSI Service Client

Used for receiving reservation confirmations/failures.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from zope.interface import implements

from twisted.python import log
from twisted.internet import defer

from opennsa.interface import NSIServiceInterface
from opennsa import error



class NSIServiceClient:

    implements(NSIServiceInterface)

    def __init__(self):
        self.reservations = {} # nsa_address -> { connection_id -> deferred }


    def addReservation(self, provider_nsa, connection_id):
        nsa_reservations = self.reservations.setdefault(provider_nsa.address, {})
        assert connection_id not in nsa_reservations

        d = defer.Deferred()
        nsa_reservations[connection_id] = d
        return d


    def abortReservation(self, provider_nsa, connection_id):
        self.reservations.setdefault(provider_nsa.address, {}).pop(connection_id)


    # command functionality

    def reserve(self, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters):
        raise error.ReservationError('Cannot invoke reserve at NSA client')

    def reservationConfirmed(self, requester_nsa, provider_nsa, global_reservation_id, description, connection_id, service_parameters):
        d = self.reservations.get(provider_nsa.address, {}).pop(connection_id, None)
        if d is None:
            print "Got reservation confirmation for non-existing reservation. NSA: %s, Id %s" % (provider_nsa.address, connection_id)
            print self.reservations
            print type(connection_id)
        else:
            d.callback(connection_id)


    def reservationFailed(self, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, service_exception):

        d = self.reservations.get(provider_nsa.address, {}).pop(connection_id, None)
        if d is None:
            print "Got reservation confirmation for non-existing reservation"
        else:
            d.callback(error)


    def terminateReservation(self, requester_nsa, provider_nsa, session_security_attr, connection_id):
        raise error.CancelReservationError('Cannot invoke cancel at NSA client')


    def provision(self, requester_nsa, provider_nsa, session_security_attr, connection_id):
        raise error.ProvisionError('Cannot invoke provision at NSA client')

    def releaseProvision(self, requester_nsa, provider_nsa, session_security_attr, connection_id):
        raise error.ReleaseProvisionError('Cannot invoke release at NSA client')


    def query(self, requester_nsa, provider_nsa, session_security_attr, query_filter):
        raise error.QueryError('Cannot invoke query at NSA client')

