"""
NRM Proxy which just logs actions performed.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import uuid

from twisted.python import log
from twisted.internet import defer

from zope.interface import implements

from opennsa import interface as nsainterface
from opennsa import error as nsaerror



class DUDNSIProxy:

    implements(nsainterface.NSIBackendInterface)

    def __init__(self, name=None):
        self.name = name
        self.reservations = {}
        self.connections = {}


    def reserve(self, source_endpoint, dest_endpoint, service_parameters):
        reservation_id = uuid.uuid1().hex[0:8]
        log.msg('RESERVE. IR ID: %s, Link: %s -> %s' % (reservation_id, source_endpoint, dest_endpoint), system='DUD Proxy. Network %s ' % self.name)
        self.reservations[reservation_id] = {} # service params can go in dict when needed
        return defer.succeed(reservation_id)


    def cancelReservation(self, reservation_id):
        try:
            self.reservations.pop(reservation_id)
            log.msg('CANCEL. IR ID: %s' % (reservation_id), system='DUD Proxy. Network %s ' % self.name)
            return defer.succeed(None)
        except KeyError:
            raise nsaerror.CancelReservationError('No such reservation (%s)' % reservation_id)


    def provision(self, reservation_id):
        # should do some time stuff sometime
        try:
            self.reservations.pop(reservation_id)
        except KeyError:
            raise nsaerror.ProvisionError('No such reservation (%s)' % reservation_id)

        connection_id = uuid.uuid1().hex[0:8]
        self.connections[connection_id] = {}
        log.msg('PROVISION. IC ID: %s, Reservation id: %s' % (connection_id, reservation_id), system='DUD Proxy. Network %s ' % self.name)
        return defer.succeed(connection_id)


    def releaseProvision(self, connection_id):
        try:
            self.connections.pop(connection_id)
        except KeyError:
            raise nsaerror.ReleaseProvisionError('No such provisioned connection (%s)' % connection_id)

        reservation_id = uuid.uuid1().hex[0:8]
        log.msg('RELEASE. IC ID: %s, IR ID: %s' % (connection_id, reservation_id), system='DUD Proxy. Network %s ' % self.name)
        self.reservations[reservation_id] = {} # service params can go in dict when needed
        return defer.succeed(reservation_id)


    def query(self, filter_attributes):
        pass


