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

import datetime

from zope.interface import implements

from twisted.python import log
from twisted.internet import reactor, defer
from twisted.application import service

from opennsa.interface import INSIProvider

from opennsa import registry, error, state, nsa
from opennsa.backends.common import scheduler, calendar

from twistar.dbobject import DBObject



class GenericBackendConnections(DBObject):
    pass



class GenericBackend(service.Service):

    implements(INSIProvider)

    TPC_TIMEOUT = 30 # seconds

    def __init__(self, network, connection_manager, parent_requester, log_system):

        self.network = network
        self.connection_manager = connection_manager
        self.parent_requester = parent_requester
        self.log_system = log_system

        self.notification_id = 0

        self.scheduler = scheduler.CallScheduler()
        self.calendar  = calendar.ReservationCalendar()
        # need to build the calendar as well

        # need to build schedule here
        self.restore_defer = defer.Deferred()
        reactor.callWhenRunning(self.buildSchedule)


    def startService(self):
        service.Service.startService(self)


    def stopService(self):
        service.Service.stopService(self)
        return self.restore_defer.addCallback( lambda _ : self.scheduler.cancelAllCalls() )


    def getNotificationId(self):
        nid = self.notification_id
        self.notification_id += 1
        return nid


    @defer.inlineCallbacks
    def buildSchedule(self):

        conns = yield GenericBackendConnections.find(where=['lifecycle_state <> ?', state.TERMINATED])
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
                if conn.provision_state == state.PROVISIONED and conn.data_plane_active == False:
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

        conns = yield GenericBackendConnections.findBy(connection_id=connection_id)
        if len(conns) == 0:
            raise error.ConnectionNonExistentError('No connection with id %s' % connection_id)
        defer.returnValue( conns[0] ) # we only get one, unique in db


    def logStateUpdate(self, conn, state_msg):
        src_target = self.connection_manager.getTarget(conn.source_port, conn.source_labels[0].type_, conn.source_labels[0].labelValue())
        dst_target = self.connection_manager.getTarget(conn.dest_port,   conn.dest_labels[0].type_,   conn.dest_labels[0].labelValue())
        log.msg('Connection %s: %s -> %s %s' % (conn.connection_id, src_target, dst_target, state_msg), system=self.log_system)


    @defer.inlineCallbacks
    def reserve(self, header, connection_id, global_reservation_id, description, service_params):

        # return defer.fail( error.InternalNRMError('test reservation failure') )

        # should perhaps verify nsa, but not that important
        log.msg('Reserve request. Connection ID: %s' % connection_id, system=self.log_system)

        if connection_id:
            raise ValueError('Cannot handle cases with existing connection id (yet)')
            #conns = yield GenericBackendConnections.findBy(connection_id=connection_id)

        # need to check schedule

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

        source_target = self.connection_manager.getTarget(source_stp.port, src_label.type_, src_label.labelValue())
        dest_target   = self.connection_manager.getTarget(dest_stp.port,   dst_label.type_, dst_label.labelValue())
        connection_id = self.connection_manager.createConnectionId(source_target, dest_target)

        # should we save the requester or provider here?
        conn = GenericBackendConnections(connection_id=connection_id, revision=0, global_reservation_id=global_reservation_id, description=description,
                                         requester_nsa=header.requester_nsa, reserve_time=now,
                                         reservation_state=state.INITIAL, provision_state=state.SCHEDULED, lifecycle_state=state.INITIAL, data_plane_active=False,
                                         source_network=source_stp.network, source_port=source_stp.port, source_labels=[src_label],
                                         dest_network=dest_stp.network, dest_port=dest_stp.port, dest_labels=[dst_label],
                                         start_time=service_params.start_time, end_time=service_params.end_time,
                                         bandwidth=service_params.bandwidth)
        yield conn.save()
        reactor.callWhenRunning(self._doReserve, conn)
        defer.returnValue(connection_id)


    @defer.inlineCallbacks
    def reserveCommit(self, header, connection_id):

        log.msg('ReserveCommit request. Connection ID: %s' % connection_id, system=self.log_system)

        conn = yield self._getConnection(connection_id, header.requester_nsa)
        if conn.lifecycle_state in (state.TERMINATING, state.TERMINATED):
            raise error.ConnectionGoneError('Connection %s has been terminated')

        yield state.reserveCommit(conn)
        self.logStateUpdate(conn, 'RESERVE COMMIT')
        yield state.reserved(conn)
        self.logStateUpdate(conn, 'RESERVED')

        yield self.parent_requester.reserveCommitConfirmed(header, connection_id)

        defer.returnValue(connection_id)


    @defer.inlineCallbacks
    def reserveAbort(self, header, connection_id):

        log.msg('ReserveAbort request. Connection ID: %s' % connection_id, system=self.log_system)

        conn = yield self._getConnection(connection_id, header.requester_nsa)
        if conn.lifecycle_state in (state.TERMINATING, state.TERMINATED):
            raise error.ConnectionGoneError('Connection %s has been terminated')

        yield self._doReserveAbort(conn)


    @defer.inlineCallbacks
    def provision(self, header, connection_id):

        conn = yield self._getConnection(connection_id, header.requester_nsa)
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

        self.parent_requester.provisionConfirmed(header, connection_id)

        defer.returnValue(conn.connection_id)


    @defer.inlineCallbacks
    def release(self, header, connection_id):

        conn = yield self._getConnection(connection_id, header.requester_nsa)
        if conn.lifecycle_state in (state.TERMINATING, state.TERMINATED):
            raise error.ConnectionGoneError('Connection %s has been terminated')

        yield state.releasing(conn)
        self.logStateUpdate(conn, 'RELEASING')

        self.scheduler.cancelCall(connection_id)

        if conn.data_plane_active:
            try:
                yield self._doTeardown(conn)
            except Exception as e:
                log.msg('Connection %s: Error tearing down link: %s' % (conn.connection_id, e))

        self.scheduler.scheduleCall(connection_id, conn.end_time, self._doTerminate, conn)
        td = conn.start_time - datetime.datetime.utcnow()
        log.msg('Connection %s: terminating scheduled for %s UTC (%i seconds)' % (conn.connection_id, conn.end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)

        yield state.scheduled(conn)
        self.logStateUpdate(conn, 'RELEASED')

        self.parent_requester.releaseConfirmed(header, connection_id)

        defer.returnValue(conn.connection_id)


    @defer.inlineCallbacks
    def terminate(self, header, connection_id):
        # return defer.fail( error.InternalNRMError('test termination failure') )

        conn = yield self._getConnection(connection_id, header.requester_nsa)
        yield self._doTerminate(conn)


    @defer.inlineCallbacks
    def querySummary(self, header, connection_ids, global_reservation_ids):
        raise NotImplementedError('QuerySummary not implemented in generic backend.')

    @defer.inlineCallbacks
    def queryRecursive(self, header, connection_ids, global_reservation_ids):
        raise NotImplementedError('QueryRecursive not implemented in generic backend.')


    @defer.inlineCallbacks
    def queryNotification(self, header, connection_id, start_notification=None, end_notification=None):
        raise NotImplementedError('QueryNotification not implemented in generic backend.')

    # --

    @defer.inlineCallbacks
    def _doReserve(self, conn):

        yield state.reserveChecking(conn)
        self.logStateUpdate(conn, 'RESERVE CHECKING')

        yield state.reserveHeld(conn)
        self.logStateUpdate(conn, 'RESERVE HELD')

        # schedule 2PC timeout
        if self.scheduler.hasScheduledCall(conn.connection_id):
            # this means that the build scheduler made a call while we yielded
            self.scheduler.cancelCall(conn.connection_id)

        now =  datetime.datetime.utcnow()
        timeout_time = min(now + datetime.timedelta(seconds=self.TPC_TIMEOUT), conn.end_time)

        self.scheduler.scheduleCall(conn.connection_id, timeout_time, self._doReserveTimeout, conn)
        td = timeout_time - datetime.datetime.utcnow()
        log.msg('Connection %s: reserve abort scheduled for %s UTC (%i seconds)' % (conn.connection_id, timeout_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)

        sc_source_stp = nsa.STP(conn.source_network, conn.source_port, conn.source_labels)
        sc_dest_stp   = nsa.STP(conn.dest_network,   conn.dest_port,   conn.dest_labels)
        sp = nsa.ServiceParameters(conn.start_time, conn.end_time, sc_source_stp, sc_dest_stp, conn.bandwidth)

        header = nsa.NSIHeader(conn.requester_nsa, conn.requester_nsa, []) # The NSA is both requester and provider in the backend, but this might be problematic without aggregator
        yield self.parent_requester.reserveConfirmed(header, conn.connection_id, conn.global_reservation_id, conn.description, sp)


    @defer.inlineCallbacks
    def _doReserveTimeout(self, conn):

        try:
            yield state.reserveTimeout(conn)
            self.logStateUpdate(conn, 'RESERVE TIMEOUT')

            yield self._doReserveAbort(conn)

            header = nsa.NSIHeader(conn.requester_nsa, conn.requester_nsa) # The NSA is both requester and provider in the backend, but this might be problematic without aggregator
            now = datetime.datetime.utcnow()
            # the conn.requesteR_nsa is somewhat problematic - the backend should really know its identity
            self.parent_requester.reserveTimeout(header, conn.connection_id, self.getNotificationId(), now, self.TPC_TIMEOUT, conn.connection_id, conn.requester_nsa)

        except Exception as e:
            log.msg('Error in reserveTimeout: %s: %s' % (type(e), e), system=self.log_system)


    @defer.inlineCallbacks
    def _doReserveAbort(self, conn):

        try:
            yield state.reserveAbort(conn)
            self.logStateUpdate(conn, 'RESERVE ABORTING')

            self.scheduler.cancelCall(conn.connection_id) # we only have this for non-timeout calls, but just cancel

            # release the resources
            src_resource = self.connection_manager.getResource(conn.source_port, conn.source_labels[0].type_, conn.source_labels[0].labelValue())
            dst_resource = self.connection_manager.getResource(conn.dest_port,   conn.dest_labels[0].type_,   conn.dest_labels[0].labelValue())

            self.calendar.removeReservation(src_resource, conn.start_time, conn.end_time)
            self.calendar.removeReservation(dst_resource, conn.start_time, conn.end_time)

            yield state.reserved(conn)
            self.logStateUpdate(conn, 'RESERVE START')

            now = datetime.datetime.utcnow()
            if now > conn.end_time:
                yield self._doTerminate(conn)
            else:
                self.scheduler.scheduleCall(conn.connection_id, conn.end_time, self._doTerminate, conn)
                td = conn.end_time - datetime.datetime.utcnow()
                log.msg('Connection %s: terminate scheduled for %s UTC (%i seconds)' % (conn.connection_id, conn.end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)

            header = nsa.NSIHeader(conn.requester_nsa, conn.requester_nsa) # The NSA is both requester and provider in the backend, but this might be problematic without aggregator
            self.parent_requester.reserveAbortConfirmed(header, conn.connection_id)

        except Exception as e:
            log.msg('Error in reserveAbort: %s: %s' % (type(e), e), system=self.log_system)


    @defer.inlineCallbacks
    def _doActivate(self, conn):

        src_target = self.connection_manager.getTarget(conn.source_port, conn.source_labels[0].type_, conn.source_labels[0].labelValue())
        dst_target = self.connection_manager.getTarget(conn.dest_port,   conn.dest_labels[0].type_,  conn.dest_labels[0].labelValue())
        try:
            yield self.connection_manager.setupLink(conn.connection_id, src_target, dst_target, conn.bandwidth)
        except Exception, e:
            # We need to mark failure in state machine here somehow....
            log.msg('Connection %s: Error setting up connection: %s' % (conn.connection_id, str(e)), system=self.log_system)
            # should include stack trace
            conn.data_plane_active = False
            yield conn.save()

            header = nsa.NSIHeader(conn.requester_nsa, conn.requester_nsa) # The NSA is both requester and provider in the backend, but this might be problematic without aggregator
            now = datetime.datetime.utcnow()
            service_ex = None
            self.parent_requester.errorEvent(header, conn.connection_id, self.getNotificationId(), now, 'activateFailed', None, service_ex)

            defer.returnValue(None)

        try:
            conn.data_plane_active = True
            yield conn.save()
            log.msg('Connection %s: Data plane activated' % (conn.connection_id), system=self.log_system)

            # we might have passed end time during activation...
            end_time = conn.end_time
            now = datetime.datetime.utcnow()
            if end_time < now:
                log.msg('Connection %s: passed end time during activation, scheduling immediate teardown.' % conn.connection_id, system=self.log_system)
                end_time = now

            self.scheduler.scheduleCall(conn.connection_id, end_time, self._doTeardown, conn)
            td = end_time - datetime.datetime.utcnow()
            log.msg('Connection %s: teardown scheduled for %s UTC (%i seconds)' % (conn.connection_id, end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)

            data_plane_status = (True, conn.revision, True) # active, version, consistent
            now = datetime.datetime.utcnow()
            header = nsa.NSIHeader(conn.requester_nsa, conn.requester_nsa) # The NSA is both requester and provider in the backend, but this might be problematic without aggregator
            self.parent_requester.dataPlaneStateChange(header, conn.connection_id, self.getNotificationId(), now, data_plane_status)
        except Exception, e:
            log.msg('Error in post-activation: %s: %s' % (type(e), e), system=self.log_system)


    @defer.inlineCallbacks
    def _doTeardown(self, conn):
        # this one is not used as a stand-alone, just a utility function

        src_target = self.connection_manager.getTarget(conn.source_port, conn.source_labels[0].type_, conn.source_labels[0].labelValue())
        dst_target = self.connection_manager.getTarget(conn.dest_port,   conn.dest_labels[0].type_,   conn.dest_labels[0].labelValue())
        try:
            yield self.connection_manager.teardownLink(conn.connection_id, src_target, dst_target, conn.bandwidth)
        except Exception, e:
            # We need to mark failure in state machine here somehow....
            log.msg('Connection %s: Error deactivating connection: %s' % (conn.connection_id, str(e)), system=self.log_system)
            # should include stack trace
            conn.data_plane_active = False # technically we don't know, but for NSI that means not active
            yield conn.save()

            header = nsa.NSIHeader(conn.requester_nsa, conn.requester_nsa) # The NSA is both requester and provider in the backend, but this might be problematic without aggregator
            now = datetime.datetime.utcnow()
            service_ex = None
            self.parent_requester.errorEvent(header, conn.connection_id, self.getNotificationId(), now, 'deactivateFailed', None, service_ex)

            defer.returnValue(None)

        try:
            conn.data_plane_active = False # technically we don't know, but for NSI that means not active
            yield conn.save()
            log.msg('Connection %s: Data planed deactivated' % (conn.connection_id), system=self.log_system)

            now = datetime.datetime.utcnow()
            data_plane_status = (False, conn.revision, True) # active, version, onsistent
            header = nsa.NSIHeader(conn.requester_nsa, conn.requester_nsa) # The NSA is both requester and provider in the backend, but this might be problematic without aggregator
            self.parent_requester.dataPlaneStateChange(header, conn.connection_id, self.getNotificationId(), now, data_plane_status)

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

        if conn.data_plane_active:
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

        header = nsa.NSIHeader(conn.requester_nsa, conn.requester_nsa, []) # The NSA is both requester and provider in the backend, but this might be problematic without aggregator
        yield self.parent_requester.terminateConfirmed(header, conn.connection_id)

