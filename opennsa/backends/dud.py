"""
NRM backends which just logs actions performed.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import uuid
import datetime

from twisted.python import log
from twisted.internet import defer

from zope.interface import implements

from opennsa import interface as nsainterface
from opennsa import error as nsaerror



ISO_DATETIME_FORMAT   = "%Y-%m-%dT%H:%M:%S:Z" # milliseconds are lacking



class _Reservation:

    def __init__(self, source_port, dest_port, start_time, end_time):
        self.source_port = source_port
        self.dest_port  = dest_port
        self.start_time = start_time
        self.end_time   = start_time



class DUDNSIBackend:

    implements(nsainterface.NSIBackendInterface)

    def __init__(self, name=None):
        self.name = name
        self.reservations = {}
        self.connections = {}


    def checkReservationFeasibility(self, source_port, dest_port, res_start, res_end):
        # check that ports are available in the specified schedule
        if res_start in [ None, '' ] or res_end in [ None, '' ]:
            raise nsaerror.ReserveError('Reservation must specify start and end time (was either None or '')')

        # sanity checks
        if res_start > res_end:
            raise nsaerror.ReserveError('Refusing to make reservation with reverse duration')

        if res_start < datetime.datetime.utcnow():
            raise nsaerror.ReserveError('Refusing to make reservation with start time in the past')

        if res_start > datetime.datetime(2020, 1, 1):
            raise nsaerror.ReserveError('Refusing to make reservation with start time after 2020')

        # port temporal availability
        def portOverlap(res1_start_time, res1_end_time, res2_start_time, res2_end_time):
            if res1_start_time >= res2_start_time and res1_start_time <= res2_end_time:
                return True
            if res1_start_time <= res2_start_time and res1_start_time <= res2_end_time:
                return True

        for res in self.reservations.values():
            if source_port in [ res.source_port, res.dest_port ]:
                if portOverlap(res.start_time, res.end_time, res_start, res_end):
                    raise nsaerror.ReserveError('Port %s not available in specified time span' % source_port)

            if dest_port == [ res.source_port, res.dest_port ]:
                if portOverlap(res.start_time, res.end_time, res_start, res_end):
                    raise nsaerror.ReserveError('Port %s not available in specified time span' % dest_port)

        # all good


    def reserve(self, source_port, dest_port, service_parameters):
        reservation_id = uuid.uuid1().hex[0:8]
        log.msg('RESERVE. IR ID: %s, Path: %s -> %s' % (reservation_id, source_port, dest_port), system='DUDBackend Network %s' % self.name)
        try:
            self.checkReservationFeasibility(source_port, dest_port, service_parameters.start_time, service_parameters.end_time)
        except nsaerror.ReserveError, e:
            return defer.fail(e)

        res = _Reservation(source_port, dest_port, service_parameters.start_time, service_parameters.end_time)
        self.reservations[reservation_id] = res
        return defer.succeed(reservation_id)


    def cancelReservation(self, reservation_id):
        try:
            self.reservations.pop(reservation_id)
            log.msg('CANCEL. IR ID: %s' % (reservation_id), system='DUDBackend Network %s' % self.name)
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
        log.msg('PROVISION. IC ID: %s, IR ID: %s' % (connection_id, reservation_id), system='DUDBackend Network %s' % self.name)
        return defer.succeed(connection_id)


    def releaseProvision(self, connection_id):
        try:
            self.connections.pop(connection_id)
        except KeyError:
            raise nsaerror.ReleaseProvisionError('No such provisioned connection (%s)' % connection_id)

        reservation_id = uuid.uuid1().hex[0:8]
        log.msg('RELEASE. IC ID: %s, IR ID: %s' % (connection_id, reservation_id), system='DUDBackend Network %s' % self.name)
        self.reservations[reservation_id] = {} # service params can go in dict when needed
        return defer.succeed(reservation_id)


    def query(self, query_filter):
        pass


