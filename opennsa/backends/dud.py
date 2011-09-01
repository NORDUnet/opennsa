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


# These state are internal to the NRM and cannot be shared with the NSI service layer
RESERVED    = 'RESERVED'
PROVISIONED = 'PROVISIONED'



class _Connection:

    def __init__(self, source_port, dest_port, start_time, end_time):
        self.source_port = source_port
        self.dest_port  = dest_port
        self.start_time = start_time
        self.end_time   = start_time
        self.state      = RESERVED


class DUDNSIBackend:

    implements(nsainterface.NSIBackendInterface)

    def __init__(self, name=None):
        self.name = name
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
            return False

        for res in self.connections.values():
            if source_port in [ res.source_port, res.dest_port ]:
                if portOverlap(res.start_time, res.end_time, res_start, res_end):
                    raise nsaerror.ReserveError('Port %s not available in specified time span' % source_port)

            if dest_port == [ res.source_port, res.dest_port ]:
                if portOverlap(res.start_time, res.end_time, res_start, res_end):
                    raise nsaerror.ReserveError('Port %s not available in specified time span' % dest_port)

        # all good


    def reserve(self, source_port, dest_port, service_parameters):
        conn_id = uuid.uuid1().hex[0:8]
        log.msg('RESERVE. ICID: %s, Ports: %s -> %s' % (conn_id, source_port, dest_port), system='DUDBackend Network %s' % self.name)
        try:
            self.checkReservationFeasibility(source_port, dest_port, service_parameters.start_time, service_parameters.end_time)
        except nsaerror.ReserveError, e:
            return defer.fail(e)

        res = _Connection(source_port, dest_port, service_parameters.start_time, service_parameters.end_time)
        self.connections[conn_id] = res
        return defer.succeed(conn_id)


    def provision(self, conn_id):
        # should do some time stuff sometime
        try:
            conn = self.connections[conn_id]
        except KeyError:
            raise nsaerror.ProvisionError('No such connection (%s)' % conn_id)

        if conn.state != RESERVED:
            raise nsaerror.ProvisionError('Cannot provision connection in state %s' % conn.state)

        conn.state = PROVISIONED
        log.msg('PROVISION. ICID: %s' % conn_id, system='DUDBackend Network %s' % self.name)
        return defer.succeed(conn_id)


    def releaseProvision(self, conn_id):
        try:
            conn = self.connections.pop(conn_id)
        except KeyError:
            raise nsaerror.ReleaseProvisionError('No such connection (%s)' % conn_id)

        if conn.state != PROVISIONED:
            raise nsaerror.ProvisionError('Cannot provision connection in state %s' % conn.state)

        conn.state = RESERVED
        log.msg('RELEASE. ICID: %s' % conn_id, system='DUDBackend Network %s' % self.name)
        self.connections[conn_id] = {} # service params can go in dict when needed
        return defer.succeed(conn_id)


    def cancelReservation(self, conn_id):
        try:
            self.connections.pop(conn_id)
            log.msg('CANCEL. ICID : %s' % (conn_id), system='DUDBackend Network %s' % self.name)
            return defer.succeed(None)
        except KeyError:
            raise nsaerror.CancelReservationError('No such reservation (%s)' % conn_id)


    def query(self, query_filter):
        pass


