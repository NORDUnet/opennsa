"""
Argia (NRA) Backend.

Uses a set of specific commands (made by Scott Campell) for making
reservations, etc. into Argia.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import os
import datetime
import StringIO

from xml.etree import ElementTree as ET

from zope.interface import implements

from twisted.python import log, failure
from twisted.internet import reactor, protocol, defer #, task

from opennsa import state, interface as nsainterface, error as nsaerror



FILE_DIR = '/srv/nsi/reservations/'

COMMAND_DIR = '/home/htj/nsi/opennsa/sandbox/argia' # temporary

RESERVE_COMMAND   = os.path.join(COMMAND_DIR, 'reserve')
PROVISION_COMMAND = os.path.join(COMMAND_DIR, 'provision')
RELEASE_COMMAND   = os.path.join(COMMAND_DIR, 'release')
CANCEL_COMMAND    = os.path.join(COMMAND_DIR, 'cancel')
QUERY_COMMAND     = os.path.join(COMMAND_DIR, 'query')



# These state are internal to the Argia NRM and cannot be shared with the NSI service layer
ARGIA_RESERVED        = 'RESERVED'
ARGIA_SCHEDULED       = 'SCHEDULED'
ARGIA_AUTO_PROVISION  = 'AUTO_PROVISION'
ARGIA_PROVISIONING    = 'PROVISIONING'
ARGIA_PROVISIONED     = 'PROVISIONED'



class ArgiaBackend:

    def __init__(self):
        self.connections = []

    def createConnection(self, source_port, dest_port, service_parameters):

        self._checkReservation(source_port, dest_port, service_parameters.start_time, service_parameters.end_time)
        ac = ArgiaConnection(source_port, dest_port, service_parameters)
        self.connections.append(ac)
        return ac


    def _checkReservation(self, source_port, dest_port, res_start, res_end):
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

        for cn in self.connections:
            csp = cn.service_parameters
            if source_port in [ cn.source_port, cn.dest_port ]:
                if portOverlap(csp.start_time, csp.end_time, res_start, res_end):
                    raise nsaerror.ReserveError('Port %s not available in specified time span' % source_port)

            if dest_port == [ cn.source_port, cn.dest_port ]:
                if portOverlap(csp.start_time, csp.end_time, res_start, res_end):
                    raise nsaerror.ReserveError('Port %s not available in specified time span' % dest_port)

        # all good



def deferTaskFailed(err):
    if err.check(defer.CancelledError):
        pass # this just means that the task was cancelled
    else:
        log.err(err)


#class _Circuit:
#
#        self.auto_provision_deferred = None
#        self.auto_release_deferred   = None
#
#
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

    def __init__(self, initial_payload=None):
        self.initial_payload = initial_payload
        self.d = defer.Deferred()

        self.stdout = StringIO.StringIO()
        self.stderr = StringIO.StringIO()

    def connectionMade(self):
        if self.initial_payload is not None:
            self.transport.write(self.initial_payload)
        self.transport.closeStdin()

    def outReceived(self, data):
        #print "OUT RECV:", data
        self.stdout.write(data)

    def errReceived(self, data):
        #print "ERR RECV:", data
        self.stderr.write(data)

    def processEnded(self, status):
        exit_code = status.value.exitCode
        #print "PROCESS EXITED:", exit_code
        self.stdout.seek(0)
        self.stderr.seek(0)
        if exit_code == 0:
            self.d.callback(self.stdout)
        else:
            self.d.errback(self.stderr)




class ArgiaConnection:

#   should implement connection interface instead - does not exist currently

    def __init__(self, source_port, dest_port, service_parameters):
        self.source_port = source_port
        self.dest_port = dest_port
        self.service_parameters = service_parameters

        self.state = state.ConnectionState()

        # this can be reservation id or connection id depending on the state, but it doesn't really matter
        self.argia_id = None


    def _constructReservationPayload(self):

        sp = self.service_parameters
        bw = sp.bandwidth_params

        root = ET.Element('reservationParameters')

        ET.SubElement(root, 'sourceEP', text=self.source_port)
        ET.SubElement(root, 'destEP', text=self.dest_port)

        bandwidth = ET.SubElement(root, 'bandwidth')
        ET.SubElement(bandwidth, 'desired').text = '1'
        if bw.minimum:
            ET.SubElement(bandwidth, 'minimum').text(str(bw.minimum))
        if bw.maximum:
            ET.SubElement(bandwidth, 'maximum').text(str(bw.maximum))

        schedule = ET.SubElement(root, 'schedule')
        ET.SubElement(schedule, 'startTime').text = sp.start_time.isoformat() + 'Z'
        ET.SubElement(schedule, 'endTime').text = sp.end_time.isoformat() + 'Z'
        #ET.dump(root
        payload = ET.tostring(root)
        return payload


    def reservation(self, _sp): #, source_port, dest_port, service_parameters):

#        conn_id = uuid.uuid1().hex[0:8]

        log.msg('RESERVE. CID: %s, Ports: %s -> %s' % (id(self), self.source_port, self.dest_port), system='ArgiaBackend')
#        try:
#            self._checkReservationFeasibility(self.source_port, self.dest_port, self.service_parameters.start_time, self.service_parameters.end_time)
#        except nsaerror.ReserveError, e:
#            return defer.fail(e)

        try:
            self.state.switchState(state.RESERVING)
        except nsaerror.ConnectionStateTransitionError:
            raise nsaerror.ReserveError('Cannot reserve connection in state %s' % self.state())
#        self.state.switchState(state.RESERVING)

        payload =  self._constructReservationPayload() #self.source_port, self.dest_port, self.service_parameters)
        process_proto = ArgiaProcessProtocol(payload)

        try:
            reactor.spawnProcess(process_proto, RESERVE_COMMAND, args=[RESERVE_COMMAND])
        except OSError, e:
            return defer.fail(nsaerror.ReserverError('Failed to invoke argia control command (%s)' % str(e)))

        d = defer.Deferred()

        def reservationConfirmed(fdata):
            log.msg('Received reservation reply from Argia. CID: %s, Ports: %s -> %s' % (id(self), self.source_port, self.dest_port), system='ArgiaBackend')
            #print "FDATA", fdata, fdata.getvalue()
            tree = ET.parse(fdata)
            argia_state = list(tree.iterfind('state'))[0].text
            reservation_id = list(tree.iterfind('reservationId'))[0].text
            #print "SR", state, reservation_id

            if argia_state != ARGIA_RESERVED:
                e = nsaerror.ReserveError('Got unexpected state from Argia (%s)' % argia_state)
                d.errback(failure.Failure(e))
                return

            self.argia_id = reservation_id
            #res = _Circuit(source_port, dest_port, service_parameters.start_time, service_parameters.end_time, reservation_id=reservation_id)
            #self.connections[conn_id] = res
            self.state.switchState(state.RESERVED)
            d.callback(self)

        def reservationFailed(fdata):
            self.state.switchState(state.TERMINATED)
            log.msg('Received reservation failure from Argia. CID: %s, Ports: %s -> %s' % (id(self), self.source_port, self.dest_port), system='ArgiaBackend')
            tree = ET.parse(fdata)
            ET.dump(tree)
            d.errback(tree)

        process_proto.d.addCallbacks(reservationConfirmed, reservationFailed)
        return d


    def provision(self):

        dt_now = datetime.datetime.utcnow()

        if self.service_parameters.end_time <= dt_now:
            raise nsaerror.ProvisionError('Cannot provision connection after end time (end time: %s, current time: %s).' % (self.service_parameters.end_time, dt_now) )


        # Argia can schedule, so we don't have to

#        elif conn.start_time > dt_now:
#            td = conn.start_time - dt_now
#            # total_seconds() is only available from python 2.7 so we use this
#            start_delta_seconds = (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6.0
#
#            conn.auto_provision_deferred = task.deferLater(reactor, start_delta_seconds, doProvision, conn)
#            conn.auto_provision_deferred.addErrback(deferTaskFailed)
#            conn.state = AUTO_PROVISION
#            log.msg('Connection %s scheduled for auto-provision in %i seconds ' % (conn_id, start_delta_seconds), system='ArgiaBackend' % self.name)

        log.msg('Provisioning connection. Start time: %s, Current time: %s).' % (self.service_parameters.start_time, dt_now), system='ArgiaBackend')

        self.state.switchState(state.PROVISIONING)
        d = defer.Deferred()

        def provisionConfirmed(fdata):
            tree = ET.parse(fdata)
            argia_state = list(tree.iterfind('state'))[0].text
            connection_id = list(tree.iterfind('connectionId'))[0].text

            if argia_state not in (ARGIA_PROVISIONED, ARGIA_AUTO_PROVISION):
                e = nsaerror.ReserveError('Got unexpected state from Argia (%s)' % argia_state)
                d.errback(failure.Failure(e))
                return

            self.state.switchState(state.PROVISIONED)
            self.argia_id = connection_id

            # schedule release
#            td = conn.end_time -  datetime.datetime.utcnow()
#            # total_seconds() is only available from python 2.7 so we use this
#            stop_delta_seconds = (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6.0

#            conn.auto_release_deferred = task.deferLater(reactor, stop_delta_seconds, self.releaseProvision, conn_id)
#            conn.auto_release_deferred.addErrback(deferTaskFailed)
            log.msg('PROVISION. CID: %s' % id(self), system='Argia')
            d.callback(self)

        def provisionFailed(fdata):
            self.state.switchState(state.TERMINATED)
            raise NotImplementedError('cannot handle failed provision yet')

        process_proto = ArgiaProcessProtocol()
        try:
            reactor.spawnProcess(process_proto, PROVISION_COMMAND, args=[PROVISION_COMMAND, self.argia_id])
        except OSError, e:
            return defer.fail(nsaerror.ReserverError('Failed to invoke argia control command (%s)' % str(e)))
        process_proto.d.addCallbacks(provisionConfirmed, provisionFailed)

        return d


    def releaseProvision(self):

        log.msg('Releasing connection. CID %s' % id(self), system='ArgiaBackend')

        try:
            self.state.switchState(state.RELEASING)
        except nsaerror.ConnectionStateTransitionError:
            raise nsaerror.ProvisionError('Cannot release connection in state %s' % self.state())

        d = defer.Deferred()

        def releaseConfirmed(fdata):
            tree = ET.parse(fdata)
            argia_state = list(tree.iterfind('state'))[0].text
            reservation_id = list(tree.iterfind('reservationId'))[0].text

            if argia_state not in (ARGIA_SCHEDULED):
                e = nsaerror.ReserveError('Got unexpected state from Argia (%s)' % argia_state)
                d.errback(failure.Failure(e))
                return

            self.state.switchState(state.SCHEDULED)
            self.argia_id = reservation_id

        def releaseFailed(fdata):
            self.state.switchState(state.TERMINATED)
            raise NotImplementedError('Argia release failure not implemented')

        process_proto = ArgiaProcessProtocol()
        try:
            reactor.spawnProcess(process_proto, RELEASE_COMMAND, args=[RELEASE_COMMAND, self.argia_id])
        except OSError, e:
            return defer.fail(nsaerror.ReleaseError('Failed to invoke argia control command (%s)' % str(e)))
        process_proto.d.addCallbacks(releaseConfirmed, releaseFailed)

        return d


    def cancelReservation(self, conn_id):
        try:
            conn = self.connections.pop(conn_id)
        except KeyError:
            raise nsaerror.CancelReservationError('No such reservation (%s)' % conn_id)

        conn.deSchedule(conn_id, 'Argia')
        log.msg('CANCEL. ICID : %s' % (conn_id), system='ArgiaBackend')
        return defer.succeed(None)


    def query(self, query_filter):
        pass


