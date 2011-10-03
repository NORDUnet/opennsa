"""
Argia (NRA) Backend.

Uses a set of specific commands (made by Scott Campell) for making
reservations, etc. into Argia.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import os
import uuid
import datetime
import StringIO

from xml.etree import ElementTree as ET

from zope.interface import implements

from twisted.python import log
#from twisted.internet import reactor, defer, task
from twisted.internet import reactor, protocol, defer



from opennsa import interface as nsainterface
from opennsa import error as nsaerror



FILE_DIR = '/srv/nsi/reservations/'

COMMAND_DIR = '/home/htj/nsi/opennsa/sandbox/argia' # temporary

RESERVE_COMMAND   = os.path.join(COMMAND_DIR, 'reserve')
PROVISION_COMMAND = os.path.join(COMMAND_DIR, 'provision')
RELEASE_COMMAND   = os.path.join(COMMAND_DIR, 'release')
CANCEL_COMMAND    = os.path.join(COMMAND_DIR, 'cancel')
QUERY_COMMAND     = os.path.join(COMMAND_DIR, 'query')



# These state are internal to the NRM and cannot be shared with the NSI service layer
RESERVED        = 'RESERVED'
AUTO_PROVISION  = 'AUTO_PROVISION'
PROVISIONED     = 'PROVISIONED'



def deferTaskFailed(err):
    if err.check(defer.CancelledError):
        pass # this just means that the task was cancelled
    else:
        log.err(err)


class _Circuit:

    def __init__(self, source_port, dest_port, start_time, end_time, reservation_id=None, connection_id=None):
        self.source_port = source_port
        self.dest_port  = dest_port
        self.start_time = start_time
        self.end_time   = end_time
        self.state      = RESERVED

        self.reservation_id = reservation_id
        self.connection_id  = connection_id

#        self.auto_provision_deferred = None
#        self.auto_release_deferred   = None


#    def deSchedule(self, conn_id, network_name=''):
#
#        if self.state == AUTO_PROVISION:
#            log.msg('Cancelling auto-provision for connection %s' % conn_id, system='Argia' % network_name)
#            self.auto_provision_deferred.cancel()
#            self.auto_provision_deferred = None
#        elif self.state == PROVISIONED:
#            log.msg('Cancelling auto-release for connection %s' % conn_id, system='Argia' % network_name)
#            self.auto_release_deferred.cancel()
#            self.auto_release_deferred = None



class ArgiaProcessProtocol(protocol.ProcessProtocol):

    def __init__(self, initial_payload):
        self.initial_payload = initial_payload
        self.d = defer.Deferred()

        self.stdout = StringIO.StringIO()
        self.stderr = StringIO.StringIO()

    def connectionMade(self):
        self.transport.write(self.initial_payload)
        self.transport.closeStdin()

    def outReceived(self, data):
        #print "OUT RECV:", data
        self.stdout.write(data)

    def errReceived(self, data):
        #print "ERR RECV:", data
        self.stderr.write(data)

    def processExited(self, status):
        exit_code = status.value.exitCode
        #print "PROCESS EXITED:", exit_code
        self.stdout.seek(0)
        self.stderr.seek(0)
        if exit_code == 0:
            self.d.callback(self.stdout)
        else:
            self.d.errback(self.stderr)



class ArgiaBackend:

    implements(nsainterface.NSIBackendInterface)

    def __init__(self, name=None):
        self.connections = {}


    def _checkReservationFeasibility(self, source_port, dest_port, res_start, res_end):
        # check that ports are available in the specified schedule
        if res_start in [ None, '' ] or res_end in [ None, '' ]:
            raise nsaerror.ReserveError('Reservation must specify start and end time (was either None or '')')

        # sanity checks
        if res_start > res_end:
            raise nsaerror.ReserveError('Refusing to make reservation with reverse duration')

        if res_start < datetime.datetime.utcnow():
            raise nsaerror.ReserveError('Refusing to make reservation with start time in the past')

        if res_start > datetime.datetime(2025, 1, 1):
            raise nsaerror.ReserveError('Refusing to make reservation with start time after 2025')

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


    def _constructReservationPayload(self, source_port, dest_port, service_parameters):

        sp = service_parameters
        bw = sp.bandwidth_params

        root = ET.Element('reservationParameters')

        ET.SubElement(root, 'sourceEP', text=source_port)
        ET.SubElement(root, 'destEP', text=dest_port)

        bandwidth = ET.SubElement(root, 'bandwidth')
        ET.SubElement(bandwidth, 'desired').text = '1'
        if bw.minimum:
            mib = ET.SubElement(bandwidth, 'minimum').text(str(bw.minimum))
        if bw.maximum:
            ET.SubElement(bandwidth, 'maximum').text(str(bw.maximum))

        schedule = ET.SubElement(root, 'schedule')
        ET.SubElement(schedule, 'startTime').text = sp.start_time.isoformat() + 'Z'
        ET.SubElement(schedule, 'endTime').text = sp.end_time.isoformat() + 'Z'
#        ET.dump(root)
        payload = ET.tostring(root)
        return payload


    def reserve(self, source_port, dest_port, service_parameters):

        conn_id = uuid.uuid1().hex[0:8]

        log.msg('RESERVE. ICID: %s, Ports: %s -> %s' % (conn_id, source_port, dest_port), system='ArgiaBackend')
        try:
            self._checkReservationFeasibility(source_port, dest_port, service_parameters.start_time, service_parameters.end_time)
        except nsaerror.ReserveError, e:
            return defer.fail(e)

        payload =  self._constructReservationPayload(source_port, dest_port, service_parameters)
        process_proto = ArgiaProcessProtocol(payload)

        try:
            pt = reactor.spawnProcess(process_proto, RESERVE_COMMAND, args=[RESERVE_COMMAND])
        except OSError, e:
            return defer.fail(nsaerror.ReserverError('Failed to invoke argia control command (%s)' % str(e)))

        d = defer.Deferred()

        def reservationConfirmed(fdata):
            log.msg('Received reservation reply from Argia. ICID: %s, Ports: %s -> %s' % (conn_id, source_port, dest_port), system='ArgiaBackend')
            tree = ET.parse(fdata)
            state = list(tree.iterfind('state'))[0].text
            reservation_id = list(tree.iterfind('reservationId'))[0].text
            #print "SR", state, reservation_id

            if state != 'RESERVED':
                e = nsaerror.ReserveError('Got unexpected state from Argia (%s)' % state)
                d.errback(failure.Failure(e))
                return

            res = _Circuit(source_port, dest_port, service_parameters.start_time, service_parameters.end_time, reservation_id=reservation_id)
            self.connections[conn_id] = res
            d.callback(conn_id)

        process_proto.d.addCallback(reservationConfirmed)
        return d


    def provision(self, conn_id):

        def doProvision(conn):
            if conn.state not in (RESERVED, AUTO_PROVISION):
                raise nsaerror.ProvisionError('Cannot provision connection in state %s' % conn.state)
            conn.state = PROVISIONED
            # schedule release
            td = conn.end_time -  datetime.datetime.utcnow()
            # total_seconds() is only available from python 2.7 so we use this
            stop_delta_seconds = (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6.0

            conn.auto_release_deferred = task.deferLater(reactor, stop_delta_seconds, self.releaseProvision, conn_id)
            conn.auto_release_deferred.addErrback(deferTaskFailed)
            log.msg('PROVISION. ICID: %s' % conn_id, system='Ariga' % self.name)
        try:
            conn = self.connections[conn_id]
        except KeyError:
            raise nsaerror.ProvisionError('No such connection (%s)' % conn_id)

        dt_now = datetime.datetime.utcnow()

        if conn.end_time <= dt_now:
            raise nsaerror.ProvisionError('Cannot provision connection after end time (end time: %s, current time: %s).' % (conn.end_time, dt_now) )
        elif conn.start_time > dt_now:
            td = conn.start_time - dt_now
            # total_seconds() is only available from python 2.7 so we use this
            start_delta_seconds = (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6.0

            conn.auto_provision_deferred = task.deferLater(reactor, start_delta_seconds, doProvision, conn)
            conn.auto_provision_deferred.addErrback(deferTaskFailed)
            conn.state = AUTO_PROVISION
            log.msg('Connection %s scheduled for auto-provision in %i seconds ' % (conn_id, start_delta_seconds), system='ArgiaBackend' % self.name)
        else:
            log.msg('Provisioning connection. Start time: %s, Current time: %s).' % (conn.start_time, dt_now), system='ArgiaBackend' % self.name)
            doProvision(conn)

        return defer.succeed(conn_id)


    def releaseProvision(self, conn_id):
        try:
            conn = self.connections[conn_id]
        except KeyError:
            raise nsaerror.ReleaseProvisionError('No such connection (%s)' % conn_id)

        if conn.state not in (AUTO_PROVISION, PROVISIONED):
            raise nsaerror.ProvisionError('Cannot release connection in state %s' % conn.state)

        conn.deSchedule(conn_id, self.name)
        conn.state = RESERVED
        log.msg('RELEASE. ICID: %s' % conn_id, system='ArgiaBackend' % self.name)
        return defer.succeed(conn_id)


    def cancelReservation(self, conn_id):
        try:
            conn = self.connections.pop(conn_id)
        except KeyError:
            raise nsaerror.CancelReservationError('No such reservation (%s)' % conn_id)

        conn.deSchedule(conn_id, self.name)
        log.msg('CANCEL. ICID : %s' % (conn_id), system='ArgiaBackend' % self.name)
        return defer.succeed(None)


    def query(self, query_filter):
        pass


