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

from opennsa import error, state, interface as nsainterface



FILE_DIR = '/srv/nsi/reservations/'

COMMAND_DIR = '/home/htj/nsi/opennsa/sandbox/argia' # temporary

RESERVE_COMMAND   = os.path.join(COMMAND_DIR, 'reserve')
PROVISION_COMMAND = os.path.join(COMMAND_DIR, 'provision')
RELEASE_COMMAND   = os.path.join(COMMAND_DIR, 'release')
TERMINATE_COMMAND = os.path.join(COMMAND_DIR, 'cancel')
QUERY_COMMAND     = os.path.join(COMMAND_DIR, 'query')



# These state are internal to the Argia NRM and cannot be shared with the NSI service layer
ARGIA_RESERVED        = 'RESERVED'
ARGIA_SCHEDULED       = 'SCHEDULED'
ARGIA_AUTO_PROVISION  = 'AUTO_PROVISION'
ARGIA_PROVISIONING    = 'PROVISIONING'
ARGIA_PROVISIONED     = 'PROVISIONED'
ARGIA_TERMINATED      = 'TERMINATED'



class ArgiaBackendError(Exception):
    """
    Raised when the Argia backend returns an error.
    """



class ArgiaBackend:

    def __init__(self):
        self.connections = []

    def createConnection(self, source_port, dest_port, service_parameters):

        self._checkTiming(service_parameters.start_time, service_parameters.end_time)
        self._checkResourceAvailability(source_port, dest_port, service_parameters.start_time, service_parameters.end_time)
        ac = ArgiaConnection(source_port, dest_port, service_parameters)
        self.connections.append(ac)
        return ac


    # this could be generic
    def _checkTiming(self, res_start, res_end):
        # check that ports are available in the specified schedule
        if res_start in [ None, '' ] or res_end in [ None, '' ]:
            raise error.InvalidRequestError('Reservation must specify start and end time (was either None or '')')

        # sanity checks
        if res_start > res_end:
            raise error.InvalidRequestError('Refusing to make reservation with reverse duration')

        if res_start < datetime.datetime.utcnow():
            raise error.InvalidRequestError('Refusing to make reservation with start time in the past')

        if res_start > datetime.datetime(2025, 1, 1):
            raise error.InvalidRequestError('Refusing to make reservation with start time after 2025')


    def _checkResourceAvailability(self, source_port, dest_port, res_start, res_end):

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
                    raise error.ResourceNotAvailableError('Port %s not available in specified time span' % source_port)

            if dest_port == [ cn.source_port, cn.dest_port ]:
                if portOverlap(csp.start_time, csp.end_time, res_start, res_end):
                    raise error.ResourceNotAvailableError('Port %s not available in specified time span' % dest_port)

        # all good



def deferTaskFailed(err):
    if err.check(defer.CancelledError):
        pass # this just means that the task was cancelled
    else:
        log.err(err)



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
            err = ArgiaBackendError('Argia command returned exit code %i' % exit_code)
            self.d.errback(err)



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
        bw = sp.bandwidth

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


    def reservation(self, _sp):

        log.msg('RESERVE. CID: %s, Ports: %s -> %s' % (id(self), self.source_port, self.dest_port), system='ArgiaBackend')

        try:
            self.state.switchState(state.RESERVING)
        except error.ConnectionStateTransitionError:
            raise error.ReserveError('Cannot reserve connection in state %s' % self.state())

        payload =  self._constructReservationPayload() #self.source_port, self.dest_port, self.service_parameters)
        process_proto = ArgiaProcessProtocol(payload)

        try:
            reactor.spawnProcess(process_proto, RESERVE_COMMAND, args=[RESERVE_COMMAND])
        except OSError, e:
            return defer.fail(error.ReserverError('Failed to invoke argia control command (%s)' % str(e)))

        d = defer.Deferred()

        def reservationConfirmed(_, pp):
            log.msg('Received reservation reply from Argia. CID: %s, Ports: %s -> %s' % (id(self), self.source_port, self.dest_port), system='ArgiaBackend')
            tree = ET.parse(pp.stdout)
            argia_state = list(tree.iterfind('state'))[0].text
            reservation_id = list(tree.iterfind('reservationId'))[0].text

            if argia_state != ARGIA_RESERVED:
                e = error.ReserveError('Got unexpected state from Argia (%s)' % argia_state)
                d.errback(failure.Failure(e))
                return

            self.argia_id = reservation_id
            self.state.switchState(state.RESERVED)
            d.callback(self)

        def reservationFailed(err, pp):
            self.state.switchState(state.TERMINATED)
            log.msg('Received reservation failure from Argia. CID: %s, Ports: %s -> %s' % (id(self), self.source_port, self.dest_port), system='ArgiaBackend')
            tree = ET.parse(pp.stderr)
            message = list(tree.iterfind('message'))[0].text
            err = error.ReserveError('Reservation failed in Argia backend: %s' % message)
            d.errback(failure.Failure(err))

        process_proto.d.addCallbacks(reservationConfirmed, reservationFailed, callbackArgs=[process_proto], errbackArgs=[process_proto])
        return d


    def provision(self):

        dt_now = datetime.datetime.utcnow()

        if self.service_parameters.end_time <= dt_now:
            raise error.ProvisionError('Cannot provision connection after end time (end time: %s, current time: %s).' % (self.service_parameters.end_time, dt_now) )


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

        def provisionConfirmed(_, pp):
            tree = ET.parse(pp.stdout)
            argia_state = list(tree.iterfind('state'))[0].text
            connection_id = list(tree.iterfind('connectionId'))[0].text

            if argia_state not in (ARGIA_PROVISIONED, ARGIA_AUTO_PROVISION):
                e = error.ReserveError('Got unexpected state from Argia (%s)' % argia_state)
                d.errback(failure.Failure(e))
                return

            self.state.switchState(state.PROVISIONED)
            self.argia_id = connection_id

            # schedule release
#            td = conn.end_time -  datetime.datetime.utcnow()
#            # total_seconds() is only available from python 2.7 so we use this
#            stop_delta_seconds = (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6.0

#            conn.auto_release_deferred = task.deferLater(reactor, stop_delta_seconds, self.release, conn_id)
#            conn.auto_release_deferred.addErrback(deferTaskFailed)
            log.msg('PROVISION. CID: %s' % id(self), system='Argia')
            d.callback(self)

        def provisionFailed(err, pp):
            tree = ET.parse(pp.stderr)
            err_msg = list(tree.iterfind('message'))[0].text
            self.state.switchState(state.TERMINATED)
            err = error.ReserveError(err_msg)
            d.errback(failure.Failure(err))

        process_proto = ArgiaProcessProtocol()
        try:
            reactor.spawnProcess(process_proto, PROVISION_COMMAND, args=[PROVISION_COMMAND, self.argia_id])
        except OSError, e:
            return defer.fail(error.ReserverError('Failed to invoke argia control command (%s)' % str(e)))
        process_proto.d.addCallbacks(provisionConfirmed, provisionFailed, callbackArgs=[process_proto], errbackArgs=[process_proto])

        return d


    def release(self):

        log.msg('Releasing connection. CID %s' % id(self), system='ArgiaBackend')

        try:
            self.state.switchState(state.RELEASING)
        except error.ConnectionStateTransitionError:
            raise error.ProvisionError('Cannot release connection in state %s' % self.state())

        d = defer.Deferred()

        def releaseConfirmed(_, process_proto):
            tree = ET.parse(process_proto.stdout)
            argia_state = list(tree.iterfind('state'))[0].text
            reservation_id = list(tree.iterfind('reservationId'))[0].text

            if argia_state not in (ARGIA_SCHEDULED):
                e = error.ReleaseError('Got unexpected state from Argia (%s)' % argia_state)
                d.errback(failure.Failure(e))
                return

            self.state.switchState(state.SCHEDULED)
            self.argia_id = reservation_id
            d.callback(self)

        def releaseFailed(err, process_proto):
            tree = ET.parse(process_proto.stdout)
            message = list(tree.iterfind('message'))[0].text
            argia_state = list(tree.iterfind('state'))[0].text

            log.msg('Error releasing conection in Argia: %s' % message, system='opennsa.ArgiaBackend')

            if argia_state == ARGIA_PROVISIONED:
                self.state.switchState(state.PROVISIONED)
            elif argia_state == ARGIA_TERMINATED:
                self.state.switchState(state.TERMINATED)
            else:
                log.msg('Unknown state returned from Argia in release faliure', system='opennsa.ArgiaBackend')

            e = error.ReleaseError('Error releasing connection: %s' % str(err))
            d.errback(e)

        process_proto = ArgiaProcessProtocol()
        try:
            reactor.spawnProcess(process_proto, RELEASE_COMMAND, args=[RELEASE_COMMAND, self.argia_id])
        except OSError, e:
            return defer.fail(error.ReleaseError('Failed to invoke argia control command (%s)' % str(e)))
        process_proto.d.addCallbacks(releaseConfirmed, releaseFailed, callbackArgs=[process_proto], errbackArgs=[process_proto])

        return d


    def terminate(self):

        log.msg('Terminating reservation. CID %s' % id(self), system='ArgiaBackend')

        try:
            self.state.switchState(state.TERMINATING)
        except error.ConnectionStateTransitionError:
            raise error.CancelReservationError('Cannot terminate connection in state %s' % self.state())

        d = defer.Deferred()

        def terminateConfirmed(_, pp):
            tree = ET.parse(pp.stdout)
            argia_state = list(tree.iterfind('state'))[0].text

            if argia_state not in (ARGIA_TERMINATED):
                e = error.ReserveError('Got unexpected state from Argia (%s)' % argia_state)
                d.errback(failure.Failure(e))
                return

            self.state.switchState(state.TERMINATED)
            self.argia_id = None
            #log.msg('CANCEL. ICID : %s' % (conn_id), system='ArgiaBackend')
            d.callback(self)

        def terminateFailed(err, pp):
            self.state.switchState(state.TERMINATED)
            raise NotImplementedError('Argia release failure not implemented')

        process_proto = ArgiaProcessProtocol()
        try:
            reactor.spawnProcess(process_proto, TERMINATE_COMMAND, args=[TERMINATE_COMMAND, self.argia_id])
        except OSError, e:
            return defer.fail(error.CancelReservationError('Failed to invoke argia control command (%s)' % str(e)))
        process_proto.d.addCallbacks(terminateConfirmed, terminateFailed, callbackArgs=[process_proto], errbackArgs=[process_proto])

        return d


    def query(self, query_filter):
        pass


