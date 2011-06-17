"""
Backend which just logs actions performed.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import uuid

from twisted.python import log
from twisted.internet import defer

from zope.interface import implements

from opennsa import interface as nsainterface
from opennsa import error as nsaerror



class DUDNSIBackend:

    implements(nsainterface.NSIBackendInterface)

    def __init__(self, name=None):
        self.name = name
        self.reservations = {}
        self.connections = {}

    def reserve(self, source_endpoint, dest_endpoint, service_parameters):
        reservation_id = uuid.uuid1().hex[0:8]
        log.msg('NSIBackend (%s): Reservation %s, %s -> %s (%s)' % (self.name, reservation_id, source_endpoint, dest_endpoint, service_parameters))
        self.reservations[reservation_id] = {} # service params can go in dict when needed
        return defer.succeed(reservation_id)


    def cancelReservation(self, reservation_id):
        try:
            self.reservations.pop(reservation_id)
            log.msg('NSIBackend (%s): Cancel reservation %s' % (self.name, reservation_id))
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
        log.msg('NSIBackend (%s): Provision %s (%s)' % (self.name, connection_id, reservation_id))
        return defer.succeed(connection_id)


    def releaseProvision(self, connection_id):
        try:
            self.connections.pop(connection_id)
        except KeyError:
            raise nsaerror.ReleaseProvisionError('No such provisioned connection (%s)' % connection_id)

        reservation_id = uuid.uuid1().hex[0:8]
        log.msg('NSIBackend (%s): Release provision %s (%s)' % (self.name, connection_id, reservation_id))
        self.reservations[reservation_id] = {} # service params can go in dict when needed
        return defer.succeed(reservation_id)


    def query(self, filter_attributes):
        pass


