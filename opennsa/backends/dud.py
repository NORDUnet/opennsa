"""
NRM backends which just logs actions performed.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import uuid
import datetime

from twisted.python import log
from twisted.internet import reactor, defer, task

from zope.interface import implements

from opennsa import interface as nsainterface
from opennsa import error as nsaerror



ISO_DATETIME_FORMAT   = "%Y-%m-%dT%H:%M:%S:Z" # milliseconds are lacking


# These state are internal to the NRM and cannot be shared with the NSI service layer
RESERVED        = 'RESERVED'
AUTO_PROVISION  = 'AUTO_PROVISION'
PROVISIONED     = 'PROVISIONED'



class _Connection:

    def __init__(self, source_port, dest_port, start_time, end_time):
        self.source_port = source_port
        self.dest_port  = dest_port
        self.start_time = start_time
        self.end_time   = end_time
        self.state      = RESERVED
        self.auto_provision_deferred = None


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

        if res_start < datetime.datetime.now():
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

        print "CONN TIMES", service_parameters.start_time, service_parameters.end_time

        res = _Connection(source_port, dest_port, service_parameters.start_time, service_parameters.end_time)
        self.connections[conn_id] = res
        return defer.succeed(conn_id)


    def provision(self, conn_id):

        def doProvision(conn):
            if conn.state not in (RESERVED, AUTO_PROVISION):
                raise nsaerror.ProvisionError('Cannot provision connection in state %s' % conn.state)
            conn.state = PROVISIONED
            log.msg('PROVISION. ICID: %s' % conn_id, system='DUDBackend Network %s' % self.name)

        def autoProvisionFailed(err):
            if err.check(defer.CancelledError):
                pass # this just means that the provision was cancelled
            else:
                log.err(err)

        try:
            conn = self.connections[conn_id]
        except KeyError:
            raise nsaerror.ProvisionError('No such connection (%s)' % conn_id)

        dt_now = datetime.datetime.now()

        if conn.end_time <= dt_now:
            raise nsaerror.ProvisionError('Cannot provision connection after end time (end time: %s, current time: %s).' % (conn.end_time, dt_now) )
        elif conn.start_time > dt_now:
            start_delta = conn.start_time - dt_now
            start_delta_seconds = start_delta.total_seconds()
            #call = reactor.callLater(start_delta_seconds, doProvision, conn)
            d = task.deferLater(reactor, start_delta_seconds, doProvision, conn)
            d.addErrback(autoProvisionFailed)
            conn.state = AUTO_PROVISION
            conn.auto_provision_deferred = d
            log.msg('Connection %s scheduled for auto-provision in %i seconds ' % (conn_id, start_delta.total_seconds()), system='DUDBackend Network %s' % self.name)
        else:
            log.msg('Provisioning connection. Start time: %s, Current time: %s).' % (conn.start_time, dt_now), system='DUDBackend Network %s' % self.name)
            doProvision(conn)

        return defer.succeed(conn_id)


    def releaseProvision(self, conn_id):
        try:
            conn = self.connections.pop(conn_id)
        except KeyError:
            raise nsaerror.ReleaseProvisionError('No such connection (%s)' % conn_id)

        if conn.state not in (AUTO_PROVISION, PROVISIONED):
            raise nsaerror.ProvisionError('Cannot provision connection in state %s' % conn.state)
        if conn.state == AUTO_PROVISION:
            log.msg('Cancelling auto-provision for connection %s' % conn_id, system='DUDBackend Network %s' % self.name)
            conn.auto_provision_deferred.cancel()
            conn.auto_provision_deferred = None

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


