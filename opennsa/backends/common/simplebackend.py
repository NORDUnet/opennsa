"""
Generic backend for deployments where OpenNSA is the only NRM (i.e. there is no
other system for interacting with the hardware).

Using this module, such a backend will only have to supply functionality for
setting up and tearing down links and does not have to deal state management.

The use this module a connection manager has to be supplied. The methods
setupLink(source_port, dest_port) and tearDown(source_port, dest_port) must be
implemented in the manager. The methods should return a deferred.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

import string
import random
import datetime

from twisted.python import log
from twisted.internet import reactor, defer
from twisted.application import service

from opennsa import registry, error, state, nsa
from opennsa.backends.common import scheduler, calendar

from twistar.dbobject import DBObject



class Simplebackendconnection(DBObject):
    pass



class SimpleBackend(service.Service):

    TPC_TIMEOUT = 30 # seconds

    def __init__(self, network, connection_manager, service_registry, log_system):

        self.network = network
        self.connection_manager = connection_manager
        self.service_registry = service_registry
        self.log_system = log_system

        self.scheduler = scheduler.CallScheduler()
        self.calendar  = calendar.ReservationCalendar()
        # need to build the calendar as well

        # the connection cache is a work-around for a race condition in mmm... something
        self.connection_cache = {}

        # need to build schedule here
        self.restore_defer = defer.Deferred()
        reactor.callWhenRunning(self.buildSchedule)


    def startService(self):
        service.Service.startService(self)

        self.service_registry.registerEventHandler(registry.RESERVE,        self.reserve,       registry.NSI2_LOCAL)
        self.service_registry.registerEventHandler(registry.RESERVE_COMMIT, self.reserveCommit, registry.NSI2_LOCAL)
        self.service_registry.registerEventHandler(registry.RESERVE_ABORT,  self.reserveAbort,  registry.NSI2_LOCAL)
        self.service_registry.registerEventHandler(registry.PROVISION,      self.provision,     registry.NSI2_LOCAL)
        self.service_registry.registerEventHandler(registry.RELEASE,        self.release,       registry.NSI2_LOCAL)
        self.service_registry.registerEventHandler(registry.TERMINATE,      self.terminate,     registry.NSI2_LOCAL)


    def stopService(self):
        service.Service.stopService(self)
        return self.restore_defer.addCallback( lambda _ : self.scheduler.cancelAllCalls() )


    @defer.inlineCallbacks
    def buildSchedule(self):

        conns = yield Simplebackendconnection.find(where=['lifecycle_state <> ?', state.TERMINATED])
        for conn in conns:
            # avoid race with newly created connections
            if self.scheduler.hasScheduledCall(conn.connection_id):
                continue

            now = datetime.datetime.utcnow()

            if conn.end_time < now and conn.lifecycle_state != state.TERMINATED:
                log.msg('Connection %s: Immediate terminate during buildSchedule' % conn.connection_id, system=self.log_system)
                yield self._doTerminate(conn)

            elif conn.start_time < now:
                if conn.provision_state == state.PROVISIONED:
                    self.scheduler.scheduleCall(conn.connection_id, conn.end_time, self._doActivate, conn)
                    td = conn.end_time - now
                    log.msg('Connection %s: activate scheduled for %s UTC (%i seconds)' % (conn.connection_id, conn.end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)
                elif conn.provision_state == state.SCHEDULED:
                    self.scheduler.scheduleCall(conn.connection_id, conn.end_time, self._doTerminate, conn)
                    td = conn.end_time - now
                    log.msg('Connection %s: terminate scheduled for %s UTC (%i seconds)' % (conn.connection_id, conn.end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)
                else:
                    log.msg('Unhandled provision state %s for connection %s in scheduler building' % (conn.provision_state, conn.connection_id))

            elif conn.start_time > now:
                if conn.provision_state == state.PROVISIONED and conn.activation_state != state.ACTIVE:
                    log.msg('Connection %s: Immediate activate during buildSchedule' % conn.connection_id, system=self.log_system)
                    yield self._doActivate(conn)
                elif conn.provision_state == state.SCHEDULED:
                    self.scheduler.scheduleCall(conn.connection_id, conn.end_time, self._doTerminate, conn)
                    td = conn.end_time - now
                    log.msg('Connection %s: terminate scheduled for %s UTC (%i seconds)' % (conn.connection_id, conn.end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)
                else:
                    log.msg('Unhandled provision state %s for connection %s in scheduler building' % (conn.provision_state, conn.connection_id))

            else:
                log.msg('Unhandled start/end time configuration for connection %s' % conn.connection_id)

        self.restore_defer.callback(None)



    @defer.inlineCallbacks
    def _getConnection(self, connection_id, requester_nsa):
        # add security check sometime
        try:
            defer.returnValue(self.connection_cache[connection_id])
        except KeyError:
            pass
        conns = yield Simplebackendconnection.findBy(connection_id=connection_id)
        if len(conns) == 0:
            raise error.ConnectionNonExistentError('No connection with id %s' % connection_id)
        self.connection_cache[connection_id] = conns[0]
        defer.returnValue( conns[0] ) # we only get one, unique in db


    def logStateUpdate(self, conn, state_msg):
        src_target = self.connection_manager.getTarget(conn.source_port, conn.source_labels[0].type_, conn.source_labels[0].labelValue())
        dst_target = self.connection_manager.getTarget(conn.dest_port,   conn.dest_labels[0].type_,   conn.dest_labels[0].labelValue())
        log.msg('Connection %s: %s -> %s %s' % (conn.connection_id, src_target, dst_target, state_msg), system=self.log_system)


    @defer.inlineCallbacks
    def reserve(self, requester_nsa, provider_nsa, session_security_attr, connection_id, global_reservation_id, description, service_params):

        # return defer.fail( error.InternalNRMError('test reservation failure') )

        # should perhaps verify nsa, but not that important

        if connection_id:
            raise ValueError('Cannot handle cases with existing connection id (yet)')
            #conns = yield Simplebackendconnection.findBy(connection_id=connection_id)

        # need to check schedule

        #connection_id = str(uuid.uuid1())
        connection_id = ''.join( [ random.choice(string.hexdigits[:16]) for _ in range(8) ] )

        source_stp = service_params.source_stp
        dest_stp   = service_params.dest_stp

        # resolve nrm ports from the topology

        if len(source_stp.labels) == 0:
            raise error.TopologyError('Source STP must specify a label')
        if len(dest_stp.labels) == 0:
            raise error.TopologyError('Destination STP must specify a label')

        if len(source_stp.labels) > 1:
            raise error.TopologyError('Source STP specifies more than one label. Only one label is currently supported')
        if len(dest_stp.labels) > 1:
            raise error.TopologyError('Destination STP specifies more than one label. Only one label is currently supported')

        src_label_candidate = source_stp.labels[0]
        dst_label_candidate = dest_stp.labels[0]
        assert src_label_candidate.type_ == dst_label_candidate.type_, 'Cannot connect ports with different label types'

        # do the: lets find the labels danace
        if self.connection_manager.canSwapLabel(src_label_candidate.type_):
            for lv in src_label_candidate.enumerateValues():
                src_resource = self.connection_manager.getResource(source_stp.port, src_label_candidate.type_, lv)
                try:
                    self.calendar.checkReservation(src_resource, service_params.start_time, service_params.end_time)
                    self.calendar.addReservation(   src_resource, service_params.start_time, service_params.end_time)
                    src_label = nsa.Label(src_label_candidate.type_, str(lv))
                    break
                except error.STPUnavailableError:
                    pass
            else:
                raise error.STPUnavailableError('STP %s not available in specified time span' % source_stp)


            for lv in dst_label_candidate.enumerateValues():
                dst_resource = self.connection_manager.getResource(dest_stp.port, dst_label_candidate.type_, lv)
                try:
                    self.calendar.checkReservation(dst_resource, service_params.start_time, service_params.end_time)
                    self.calendar.addReservation(   dst_resource, service_params.start_time, service_params.end_time)
                    dst_label = nsa.Label(dst_label_candidate.type_, str(lv))
                    break
                except error.STPUnavailableError:
                    pass
            else:
                raise error.STPUnavailableError('STP %s not available in specified time span' % dest_stp)

        else:
            label_candidate = src_label_candidate.intersect(dst_label_candidate)

            for lv in label_candidate.enumerateValues():
                src_resource = self.connection_manager.getResource(source_stp.port, label_candidate.type_, lv)
                dst_resource = self.connection_manager.getResource(dest_stp.port,   label_candidate.type_, lv)
                try:
                    self.calendar.checkReservation(src_resource, service_params.start_time, service_params.end_time)
                    self.calendar.checkReservation(dst_resource, service_params.start_time, service_params.end_time)
                    self.calendar.addReservation(   src_resource, service_params.start_time, service_params.end_time)
                    self.calendar.addReservation(   dst_resource, service_params.start_time, service_params.end_time)
                    src_label = nsa.Label(label_candidate.type_, str(lv))
                    dst_label = nsa.Label(label_candidate.type_, str(lv))
                    break
                except error.STPUnavailableError:
                    pass
            else:
                raise error.STPUnavailableError('STP combination %s and %s not available in specified time span' % (source_stp, dest_stp))

        now =  datetime.datetime.utcnow()

        # should we save the requester or provider here?
        conn = Simplebackendconnection(connection_id=connection_id, revision=0, global_reservation_id=global_reservation_id, description=description,
                                       requester_nsa=provider_nsa.urn(), reserve_time=now,
                                       reservation_state=state.INITIAL, provision_state=state.SCHEDULED, activation_state=state.INACTIVE, lifecycle_state=state.INITIAL,
                                       source_network=source_stp.network, source_port=source_stp.port, source_labels=[src_label],
                                       dest_network=dest_stp.network, dest_port=dest_stp.port, dest_labels=[dst_label],
                                       start_time=service_params.start_time, end_time=service_params.end_time,
                                       bandwidth=service_params.bandwidth)
        yield conn.save()

        # this sould really be much earlier, need to save connection before checking
        yield state.reserveChecking(conn)
        self.logStateUpdate(conn, 'RESERVE CHECKING')

        yield state.reserveHeld(conn)
        self.logStateUpdate(conn, 'RESERVE HELD')

        # schedule 2PC timeout
        if self.scheduler.hasScheduledCall(conn.connection_id):
            # this means that the build scheduler made a call while we yielded
            self.scheduler.cancelCall(connection_id)

        timeout_time = min(now + datetime.timedelta(seconds=self.TPC_TIMEOUT), conn.end_time)

        self.scheduler.scheduleCall(connection_id, timeout_time, self._doReserveTimeout, conn)
        td = timeout_time - datetime.datetime.utcnow()
        log.msg('Connection %s: reserve abort scheduled for %s UTC (%i seconds)' % (conn.connection_id, timeout_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)

        sc_source_stp = nsa.STP(source_stp.network, source_stp.port, labels=[src_label])
        sc_dest_stp   = nsa.STP(dest_stp.network,   dest_stp.port,   labels=[dst_label])
        sp = nsa.ServiceParameters(service_params.start_time, service_params.end_time, sc_source_stp, sc_dest_stp, service_params.bandwidth)
        rig = (global_reservation_id, description, connection_id, sp)
        defer.returnValue(rig)


    @defer.inlineCallbacks
    def reserveCommit(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        conn = yield self._getConnection(connection_id, requester_nsa)
        if conn.lifecycle_state in (state.TERMINATING, state.TERMINATED):
            raise error.ConnectionGoneError('Connection %s has been terminated')

        yield state.reserveCommit(conn)
        yield state.reserved(conn)


    @defer.inlineCallbacks
    def reserveAbort(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        conn = yield self._getConnection(connection_id, requester_nsa)
        if conn.lifecycle_state in (state.TERMINATING, state.TERMINATED):
            raise error.ConnectionGoneError('Connection %s has been terminated')

        yield self._doReserveAbort(conn)


    @defer.inlineCallbacks
    def provision(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        conn = yield self._getConnection(connection_id, requester_nsa)
        if conn.lifecycle_state in (state.TERMINATING, state.TERMINATED):
            raise error.ConnectionGoneError('Connection %s has been terminated')

        if conn.reservation_state != state.RESERVED:
            raise error.InvalidTransitionError('Cannot provision connection in a non-reserved state')

        now = datetime.datetime.utcnow()
        if conn.end_time <= now:
            raise error.ConnectionGone('Cannot provision connection after end time (end time: %s, current time: %s).' % (conn.end_time, now))

        yield state.provisioning(conn)
        self.logStateUpdate(conn, 'PROVISIONING')

        self.scheduler.cancelCall(connection_id)

        if conn.start_time <= now:
            d = self._doActivate(conn)
        else:
            self.scheduler.scheduleCall(connection_id, conn.start_time, self._doActivate, conn)
            td = conn.start_time - now
            log.msg('Connection %s: activate scheduled for %s UTC (%i seconds)' % (conn.connection_id, conn.end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)

        yield state.provisioned(conn)
        self.logStateUpdate(conn, 'PROVISIONED')
        defer.returnValue(conn.connection_id)


    @defer.inlineCallbacks
    def release(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        conn = yield self._getConnection(connection_id, requester_nsa)
        if conn.lifecycle_state in (state.TERMINATING, state.TERMINATED):
            raise error.ConnectionGoneError('Connection %s has been terminated')

        yield state.releasing(conn)
        self.logStateUpdate(conn, 'RELEASING')

        self.scheduler.cancelCall(connection_id)

        if conn.activation_state == state.ACTIVE:
            try:
                yield self._doTeardown(conn)
            except Exception as e:
                log.msg('Connection %s: Error tearing down link: %s' % (conn.connection_id, e))

        self.scheduler.scheduleCall(connection_id, conn.end_time, self._doTerminate, conn)
        td = conn.start_time - datetime.datetime.utcnow()
        log.msg('Connection %s: terminating scheduled for %s UTC (%i seconds)' % (conn.connection_id, conn.end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)

        yield state.scheduled(conn)
        self.logStateUpdate(conn, 'RELEASED')
        defer.returnValue(conn.connection_id)


    @defer.inlineCallbacks
    def terminate(self, requester_nsa, provider_nsa, session_security_attr, connection_id):
        # return defer.fail( error.InternalNRMError('test termination failure') )

        conn = yield self._getConnection(connection_id, requester_nsa)
        yield self._doTerminate(conn)


    def query(self, query_filter):
        pass


    @defer.inlineCallbacks
    def _doReserveTimeout(self, conn):

        yield state.reserveTimeout(conn)
        self.logStateUpdate(conn, 'RESERVE TIMEOUT')

        yield self._doReserveAbort(conn)

        connection_states = (conn.reservation_state, conn.provision_state, conn.lifecycle_state, conn.activation_state)
        reserve_timeout = self.service_registry.getHandler(registry.RESERVE_TIMEOUT, registry.NSI2_LOCAL)

        reserve_timeout(conn.connection_id, connection_states, self.TPC_TIMEOUT, datetime.datetime.utcnow())


    @defer.inlineCallbacks
    def _doReserveAbort(self, conn):

        yield state.reserveAbort(conn)
        self.logStateUpdate(conn, 'RESERVE ABORTING')

        self.scheduler.cancelCall(conn.connection_id) # we only have this for non-timeout calls, but just cancel

        # release the resources
        src_resource = self.connection_manager.getResource(conn.source_port, conn.source_labels[0].type_, conn.source_labels[0].labelValue())
        dst_resource = self.connection_manager.getResource(conn.dest_port,   conn.dest_labels[0].type_,   conn.dest_labels[0].labelValue())

        self.calendar.removeReservation(src_resource, conn.start_time, conn.end_time)
        self.calendar.removeReservation(dst_resource, conn.start_time, conn.end_time)

        yield state.reserved(conn)
        self.logStateUpdate(conn, 'RESERVE INITIAL')

        now = datetime.datetime.utcnow()
        if now > conn.end_time:
            yield self._doTerminate(conn)
        else:
            self.scheduler.scheduleCall(conn.connection_id, conn.end_time, self._doTerminate, conn)
            td = conn.end_time - datetime.datetime.utcnow()
            log.msg('Connection %s: terminate scheduled for %s UTC (%i seconds)' % (conn.connection_id, conn.end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)


    @defer.inlineCallbacks
    def _doActivate(self, conn):

        if conn.activation_state != state.ACTIVATING: # We died during a previous activate somehow
            yield state.activating(conn)
            self.logStateUpdate(conn, 'ACTIVATING')

        src_target = self.connection_manager.getTarget(conn.source_port, conn.source_labels[0].type_, conn.source_labels[0].labelValue())
        dst_target = self.connection_manager.getTarget(conn.dest_port,   conn.dest_labels[0].type_,  conn.dest_labels[0].labelValue())
        try:
            yield self.connection_manager.setupLink(src_target, dst_target)
        except Exception, e:
            # We need to mark failure in state machine here somehow....
            log.msg('Connection %s: Error setting up connection: %s' % (conn.connection_id, str(e)), system=self.log_system)
            # should include stack trace
            yield state.inactive(conn)
            self.logStateUpdate(conn, 'INACTIVE')

            error_event = self.service_registry.getHandler(registry.ERROR_EVENT, registry.NSI2_LOCAL)
            connection_states = (conn.reservation_state, conn.provision_state, conn.lifecycle_state, conn.activation_state)
            service_ex = (None, type(e), str(e), None, None)
            error_event(conn.connection_id, 'activateFailed', connection_states, datetime.datetime.utcnow(), str(e), service_ex)

            defer.returnValue(None)

        try:
            yield state.active(conn)
            self.logStateUpdate(conn, 'ACTIVE')
            self.scheduler.scheduleCall(conn.connection_id, conn.end_time, self._doTerminate, conn)
            td = conn.end_time - datetime.datetime.utcnow()
            log.msg('Connection %s: terminate scheduled for %s UTC (%i seconds)' % (conn.connection_id, conn.end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)

            data_plane_change = self.service_registry.getHandler(registry.DATA_PLANE_CHANGE, registry.NSI2_LOCAL)
            dps = (True, conn.revision, True) # data plane status - active, version, version consistent
            data_plane_change(conn.connection_id, dps, datetime.datetime.utcnow())
        except Exception, e:
            # this really should not happen
            log.msg('Error in post-activation: %s' % e)


    @defer.inlineCallbacks
    def _doTeardown(self, conn):
        # this one is not used as a stand-alone, just a utility function
        yield state.deactivating(conn)
        self.logStateUpdate(conn, 'DEACTIVATING')

        src_target = self.connection_manager.getTarget(conn.source_port, conn.source_labels[0].type_, conn.source_labels[0].labelValue())
        dst_target = self.connection_manager.getTarget(conn.dest_port,   conn.dest_labels[0].type_,   conn.dest_labels[0].labelValue())
        try:
            yield self.connection_manager.teardownLink(src_target, dst_target)
        except Exception, e:
            # We need to mark failure in state machine here somehow....
            log.msg('Connection %s: Error deactivating connection: %s' % (conn.connection_id, str(e)), system=self.log_system)
            # should include stack trace
            yield state.inactive(conn)
            self.logStateUpdate(conn, 'INACTIVE')

            error_event = self.service_registry.getHandler(registry.ERROR_EVENT, registry.NSI2_LOCAL)
            connection_states = (conn.reservation_state, conn.provision_state, conn.lifecycle_state, conn.activation_state)
            service_ex = (None, type(e), str(e), None, None)
            error_event(conn.connection_id, 'deactivateFailed', connection_states, datetime.datetime.utcnow(), str(e), service_ex)

            defer.returnValue(None)

        try:
            yield state.inactive(conn)
            self.logStateUpdate(conn, 'INACTIVE')
            data_plane_change = self.service_registry.getHandler(registry.DATA_PLANE_CHANGE, registry.NSI2_LOCAL)
            dps = (False, conn.revision, True) # data plane status - active, version, version consistent
            data_plane_change(conn.connection_id, dps, datetime.datetime.utcnow())
        except Exception as e:
            log.msg('Error in post-deactivation: %s' % e)


    @defer.inlineCallbacks
    def _doTerminate(self, conn):

        if conn.lifecycle_state == state.TERMINATED:
            defer.returnValue(conn.cid)

        # this allows connections stuck in terminating to terminate
        if conn.lifecycle_state == state.INITIAL:
            yield state.terminating(conn)
            self.logStateUpdate(conn, 'TERMINATING')

        self.scheduler.cancelCall(conn.connection_id)

        if conn.activation_state == state.ACTIVE:
            try:
                yield self._doTeardown(conn)
                # we can only remove resource reservation entry if we succesfully shut down the link :-(
                src_resource = self.connection_manager.getResource(conn.source_port, conn.source_labels[0].type_, conn.source_labels[0].labelValue())
                dst_resource = self.connection_manager.getResource(conn.dest_port,   conn.dest_labels[0].type_,   conn.dest_labels[0].labelValue())
                self.calendar.removeReservation(src_resource, conn.start_time, conn.end_time)
                self.calendar.removeReservation(dst_resource, conn.start_time, conn.end_time)
            except Exception as e:
                log.msg('Error terminating connection: %s' % e)
                raise e

        yield state.terminated(conn)
        self.logStateUpdate(conn, 'TERMINATED')
        defer.returnValue(conn.connection_id)

