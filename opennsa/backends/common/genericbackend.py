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

from zope.interface import implementer

from twisted.python import log
from twisted.internet import reactor, defer
from twisted.application import service

from opennsa.interface import INSIProvider

from opennsa import constants as cnt, error, state, nsa, authz
from opennsa.backends.common import scheduler, calendar

from twistar.dbobject import DBObject



class GenericBackendConnections(DBObject):
    pass



@implementer(INSIProvider)
class GenericBackend(service.Service):

    # This is how long a reservation will be kept in reserved, but not committed state.
    # Two minutes (120 seconds) is the recommended value from the NSI group
    # Yeah, it should be much less, but some NRMs are that slow
    TPC_TIMEOUT = 120 # seconds

    def __init__(self, network, nrm_ports, connection_manager, parent_requester, log_system, minimum_duration=60):

        self.network            = network
        self.nrm_ports          = nrm_ports
        self.connection_manager = connection_manager
        self.parent_requester   = parent_requester
        self.log_system         = log_system
        self.minimum_duration   = minimum_duration

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
        if self.restore_defer.called:
            self.scheduler.cancelAllCalls()
            return defer.succeed(None)
        else:
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

            if conn.lifecycle_state in (state.PASSED_ENDTIME, state.TERMINATED):
                continue # This connection has already lived it life to the fullest :-)

            if conn.reservation_state == state.RESERVE_START and not conn.allocated:
                # This happens when a connection was reserved, but never committed and abort/timeout happened
                log.msg('Connection %s: Was never comitted, not putting entry into calendar' % conn.connection_id, debug=True, system=self.log_system)
                continue

            # add reservation, some of the following code will remove the reservation again
            src_resource = self.connection_manager.getResource(conn.source_port, conn.source_label)
            dst_resource = self.connection_manager.getResource(conn.dest_port,   conn.dest_label)
            self.calendar.addReservation(  src_resource, conn.start_time, conn.end_time)
            self.calendar.addReservation(  dst_resource, conn.start_time, conn.end_time)

            if conn.end_time is not None and conn.end_time < now and conn.lifecycle_state not in (state.PASSED_ENDTIME, state.TERMINATED):
                log.msg('Connection %s: Immediate end during buildSchedule' % conn.connection_id, system=self.log_system)
                yield self._doEndtime(conn)
                continue

            elif conn.reservation_state == state.RESERVE_HELD:
                abort_time = conn.reserve_time + datetime.timedelta(seconds=self.TPC_TIMEOUT)
                timeout_time = min(abort_time, conn.end_time or abort_time) # or to handle None case
                if timeout_time < now:
                    # have passed the time when timeout should occur
                    log.msg('Connection %s: Reservation Held, but timeout has passed, doing rollback' % conn.connection_id, system=self.log_system)
                    yield self._doReserveRollback(conn) # will remove reservation
                else:
                    td = timeout_time - now
                    log.msg('Connection %s: Reservation Held, scheduling timeout in %i seconds' % (conn.connection_id, td.total_seconds()), system=self.log_system)
                    self.scheduler.scheduleCall(conn.connection_id, timeout_time, self._doReserveTimeout, conn)

            elif conn.start_time is None or conn.start_time < now:
                # we have passed start time, we must either: activate, schedule deactive, or schedule terminate
                if conn.provision_state == state.PROVISIONED:
                    if conn.data_plane_active:
                        if conn.end_time is None:
                            log.msg('Connection %s: already active, no scheduled end time' % conn.connection_id, system=self.log_system)
                        else:
                            self.scheduler.scheduleCall(conn.connection_id, conn.end_time, self._doEndtime, conn)
                            td = conn.end_time - now
                            log.msg('Connection %s: already active, scheduling end for %s UTC (%i seconds) (buildSchedule)' % (conn.connection_id, conn.end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)
                    else:
                        log.msg('Connection %s: Immediate activate during buildSchedule' % conn.connection_id, system=self.log_system)
                        yield self._doActivate(conn)
                elif conn.provision_state == state.RELEASED:
                    if conn.end_time is None:
                        log.msg('Connection %s: Currently released, no end scheduled' % conn.connection_id, system=self.log_system)
                    else:
                        self.scheduler.scheduleCall(conn.connection_id, conn.end_time, self._doEndtime, conn)
                        td = conn.end_time - now
                        log.msg('Connection %s: End scheduled for %s UTC (%i seconds) (buildSchedule)' % (conn.connection_id, conn.end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)
                else:
                    log.msg('Unhandled provision state %s for connection %s in scheduler building' % (conn.provision_state, conn.connection_id))

            elif conn.start_time > now:
                # start time has not yet passed, we must schedule activate or schedule terminate depending on state
                if conn.provision_state == state.PROVISIONED and conn.data_plane_active == False:
                    self.scheduler.scheduleCall(conn.connection_id, conn.start_time, self._doActivate, conn)
                    td = conn.start_time - now
                    log.msg('Connection %s: activate scheduled for %s UTC (%i seconds) (buildSchedule)' % (conn.connection_id, conn.end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)
                elif conn.provision_state == state.RELEASED:
                    self.scheduler.scheduleCall(conn.connection_id, conn.end_time, self._doEndtime, conn)
                    td = conn.end_time - now
                    log.msg('Connection %s: End scheduled for %s UTC (%i seconds) (buildSchedule)' % (conn.connection_id, conn.end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)
                else:
                    log.msg('Unhandled provision state %s for connection %s in scheduler building' % (conn.provision_state, conn.connection_id))

            else:
                log.msg('Unhandled start/end time configuration for connection %s' % conn.connection_id, system=self.log_system)

        log.msg('Scheduled calls restored', system=self.log_system)
        self.restore_defer.callback(None)



    @defer.inlineCallbacks
    def _getConnection(self, connection_id, requester_nsa):
        # add security check sometime

        conns = yield GenericBackendConnections.findBy(connection_id=connection_id)
        if len(conns) == 0:
            raise error.ConnectionNonExistentError('No connection with id %s' % connection_id)
        defer.returnValue( conns[0] ) # we only get one, unique in db


    def _authorize(self, source_port, destination_port, header, request_info, start_time=None, end_time=None):
        """
        Checks if port usage is allowed from the credentials provided in the
        NSI header or information from the request.
        """
        nrm_source_port = self.nrm_ports[source_port]
        nrm_dest_port   = self.nrm_ports[destination_port]

        source_authz = authz.isAuthorized(nrm_source_port, header.security_attributes, request_info, nrm_source_port, None, None)
        if not source_authz:
            stp_name = cnt.URN_OGF_PREFIX + self.network + ':' + nrm_source_port.name
            raise error.UnauthorizedError('Request does not have any valid credentials for STP %s' % stp_name)

        dest_authz = authz.isAuthorized(nrm_dest_port, header.security_attributes, request_info, nrm_dest_port, None, None)
        if not dest_authz:
            stp_name = cnt.URN_OGF_PREFIX + self.network + ':' + nrm_dest_port.name
            raise error.UnauthorizedError('Request does not have any valid credentials for STP %s' % stp_name)


    def logStateUpdate(self, conn, state_msg):
        src_target = self.connection_manager.getTarget(conn.source_port, conn.source_label)
        dst_target = self.connection_manager.getTarget(conn.dest_port,   conn.dest_label)
        log.msg('Connection %s: %s -> %s %s' % (conn.connection_id, src_target, dst_target, state_msg), system=self.log_system)


    @defer.inlineCallbacks
    def reserve(self, header, connection_id, global_reservation_id, description, criteria, request_info=None):

        # return defer.fail( error.InternalNRMError('test reservation failure') )

        sd = criteria.service_def

        if type(sd) is not nsa.Point2PointService:
            raise ValueError('Cannot handle service of type %s, only Point2PointService is currently supported' % type(sd))

        # should perhaps verify nsa, but not that important
        log.msg('Reserve request. Connection ID: %s' % connection_id, system=self.log_system)

        if connection_id:
            # if connection id is specified it is not allowed to be used a priori
            try:
                conn = yield self._getConnection(connection_id, header.requester_nsa)
                raise ValueError('GenericBackend cannot handle modify (yet)')
            except error.ConnectionNonExistentError:
                pass # expected

        source_stp = sd.source_stp
        dest_stp   = sd.dest_stp

        # check network and ports exist

        if source_stp.network != self.network:
            raise error.ConnectionCreateError('Source network does not match network this NSA is managing (%s != %s)' % (source_stp.network, self.network) )
        if dest_stp.network != self.network:
            raise error.ConnectionCreateError('Destination network does not match network this NSA is managing (%s != %s)' % (dest_stp.network, self.network) )

        # ensure that ports actually exists
        if not source_stp.port in self.nrm_ports:
            raise error.STPUnavailableError('No STP named %s (ports: %s)' %(source_stp.baseURN(), str(self.nrm_ports.keys()) ))
        if not dest_stp.port in self.nrm_ports:
            raise error.STPUnavailableError('No STP named %s (ports: %s)' %(dest_stp.baseURN(), str(self.nrm_ports.keys()) ))

        start_time = criteria.schedule.start_time # or datetime.datetime.utcnow().replace(microsecond=0) + datetime.timedelta(seconds=1)  # no start time = now (well, in 1 second)
        end_time   = criteria.schedule.end_time

        if start_time is not None and end_time is not None:
            duration = (end_time - start_time).total_seconds()
            if duration < self.minimum_duration:
                raise error.ConnectionCreateError('Duration too short, minimum duration is %i seconds (%i specified)' % (self.minimum_duration, duration), self.network)

        nrm_source_port = self.nrm_ports[source_stp.port]
        nrm_dest_port   = self.nrm_ports[dest_stp.port]

        self._authorize(source_stp.port, dest_stp.port, header, request_info, start_time, end_time)

        # transit restriction
        if nrm_source_port.transit_restricted and nrm_dest_port.transit_restricted:
            raise error.ConnectionCreateError('Cannot connect two transit restricted STPs.')

        # check that we are not connecting two identical stp (hairpin)
        if source_stp.port == dest_stp.port and source_stp.label == dest_stp.label:
            raise error.ServiceError('Cannot connect STP %s to itself.' % source_stp)

        labelType = lambda stp : None if stp.label is None else stp.label.type_

        # have the backend check if the ports/labels can be connected
        # this is needed for cases of cross-label switching like ethernet-mpls encapsulation
        if hasattr(self.connection_manager, 'canConnect'):
            if not self.connection_manager.canConnect(source_stp.port, dest_stp.port, source_stp.label, dest_stp.label):
                raise error.TopologyError('Cannot connect STP %s to %s.' % (source_stp, dest_stp))
        elif labelType(source_stp) != labelType(dest_stp):
            # if backend doesn't implement canConnect, we assume only the same label can be connected (old default)
            raise error.TopologyError('Cannot connect ports with different label types')


        # now check that the ports have (some of) the specified label values
        if not nsa.Label.canMatch(nrm_source_port.label, source_stp.label):
            raise error.TopologyError('Source port %s cannot match label set %s' % (nrm_source_port.name, source_stp.label) )
        if not nsa.Label.canMatch(nrm_dest_port.label, dest_stp.label):
            raise error.TopologyError('Destination port %s cannot match label set %s' % (nrm_dest_port.name, dest_stp.label) )

        labelEnum = lambda label : [None] if label is None else [ nsa.Label(label.type_, lv) for lv in label.enumerateValues() ]

        # do the find the label value dance
        if self.connection_manager.canSwapLabel(labelType(source_stp)) and self.connection_manager.canSwapLabel(labelType(dest_stp)):
            for lv in labelEnum(source_stp.label):
                src_resource = self.connection_manager.getResource(source_stp.port, lv)
                try:
                    self.calendar.checkReservation(src_resource, start_time, end_time)
                    src_label = lv
                    break
                except error.STPUnavailableError:
                    pass
            else:
                raise error.STPUnavailableError('STP %s not available in specified time span' % source_stp)

            for lv in labelEnum(dest_stp.label):
                dst_resource = self.connection_manager.getResource(dest_stp.port, lv)
                try:
                    self.calendar.checkReservation(dst_resource, start_time, end_time)
                    dst_label = lv
                    break
                except error.STPUnavailableError:
                    pass
            else:
                raise error.STPUnavailableError('STP %s not available in specified time span' % dest_stp)

            # Only add reservations, when src and dest stps are both available
            self.calendar.addReservation(  src_resource, start_time, end_time)
            self.calendar.addReservation(  dst_resource, start_time, end_time)

        else:
            if source_stp.label is None:
                label_candidate = dest_stp.label
            elif dest_stp.label is None:
                label_candidate = source_stp.label
            else:
                try:
                    label_candidate = source_stp.label.intersect(dest_stp.label)
                except nsa.EmptyLabelSet:
                    raise error.VLANInterchangeNotSupportedError('VLAN re-write not supported and no possible label intersection')

            for lv in labelEnum(label_candidate):
                src_resource = self.connection_manager.getResource(source_stp.port, lv)
                dst_resource = self.connection_manager.getResource(dest_stp.port,   lv)
                try:
                    self.calendar.checkReservation(src_resource, start_time, end_time)
                    self.calendar.checkReservation(dst_resource, start_time, end_time)
                    self.calendar.addReservation(  src_resource, start_time, end_time)
                    self.calendar.addReservation(  dst_resource, start_time, end_time)
                    src_label = lv
                    dst_label = lv
                    break
                except error.STPUnavailableError:
                    continue
            else:
                raise error.STPUnavailableError('Link %s and %s not available in specified time span' % (source_stp, dest_stp))

        now =  datetime.datetime.utcnow()

        source_target = self.connection_manager.getTarget(source_stp.port, src_label)
        dest_target   = self.connection_manager.getTarget(dest_stp.port,   dst_label)
        if connection_id is None:
            connection_id = self.connection_manager.createConnectionId(source_target, dest_target)

        # we should check the schedule here

        # should we save the requester or provider here?
        conn = GenericBackendConnections(connection_id=connection_id, revision=0, global_reservation_id=global_reservation_id, description=description,
                                         requester_nsa=header.requester_nsa, reserve_time=now,
                                         reservation_state=state.RESERVE_START, provision_state=state.RELEASED, lifecycle_state=state.CREATED, data_plane_active=False,
                                         source_network=source_stp.network, source_port=source_stp.port, source_label=src_label,
                                         dest_network=dest_stp.network, dest_port=dest_stp.port, dest_label=dst_label,
                                         start_time=start_time, end_time=end_time,
                                         symmetrical=sd.symmetric, directionality=sd.directionality, bandwidth=sd.capacity, allocated=False)
        yield conn.save()
        reactor.callWhenRunning(self._doReserve, conn, header.correlation_id)
        defer.returnValue(connection_id)


    @defer.inlineCallbacks
    def reserveCommit(self, header, connection_id, request_info=None):

        log.msg('ReserveCommit request from %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=self.log_system)

        conn = yield self._getConnection(connection_id, header.requester_nsa)
        self._authorize(conn.source_port, conn.dest_port, header, request_info)

        if conn.lifecycle_state in (state.TERMINATING, state.TERMINATED):
            raise error.ConnectionGoneError('Connection %s has been terminated')

        # the switch to reserve start and allocated must be in same transaction
        # state.reserveMultiSwitch will save the state, including the allocated flag
        conn.allocated = True
        yield state.reserveMultiSwitch(conn, state.RESERVE_COMMITTING, state.RESERVE_START)

        self.logStateUpdate(conn, 'COMMIT/RESERVED')

        # cancel abort and schedule end time call
        self.scheduler.cancelCall(connection_id)
        if conn.end_time is not None:
            self.scheduler.scheduleCall(conn.connection_id, conn.end_time, self._doEndtime, conn)
            td = conn.end_time - datetime.datetime.utcnow()
            log.msg('Connection %s: End and teardown scheduled for %s UTC (%i seconds)' % (conn.connection_id, conn.end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)

        yield self.parent_requester.reserveCommitConfirmed(header, connection_id)

        defer.returnValue(connection_id)


    @defer.inlineCallbacks
    def reserveAbort(self, header, connection_id, request_info=None):

        log.msg('ReserveAbort request from %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=self.log_system)

        conn = yield self._getConnection(connection_id, header.requester_nsa)
        self._authorize(conn.source_port, conn.dest_port, header, request_info)

        if conn.lifecycle_state in (state.TERMINATING, state.TERMINATED):
            raise error.ConnectionGoneError('Connection %s has been terminated')

        yield self._doReserveRollback(conn)

        header = nsa.NSIHeader(conn.requester_nsa, conn.requester_nsa) # The NSA is both requester and provider in the backend, but this might be problematic without aggregator
        self.parent_requester.reserveAbortConfirmed(header, conn.connection_id)


    @defer.inlineCallbacks
    def provision(self, header, connection_id, request_info=None):

        log.msg('Provision request from %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=self.log_system)

        conn = yield self._getConnection(connection_id, header.requester_nsa)
        self._authorize(conn.source_port, conn.dest_port, header, request_info)

        if not conn.allocated:
            raise error.ConnectionError('No resource allocated to the connection, cannot provision')

        if conn.lifecycle_state in (state.TERMINATING, state.TERMINATED):
            raise error.ConnectionGoneError('Connection %s has been terminated')

        if conn.reservation_state != state.RESERVE_START:
            raise error.InvalidTransitionError('Cannot provision connection in a non-reserved state')

        now = datetime.datetime.utcnow()
        if conn.end_time is not None and conn.end_time <= now:
            raise error.ConnectionGoneError('Cannot provision connection after end time (end time: %s, current time: %s).' % (conn.end_time, now))

        yield state.provisioning(conn)
        self.logStateUpdate(conn, 'PROVISIONING')

        self.scheduler.cancelCall(connection_id)

        if conn.start_time is None or conn.start_time <= now:
            self._doActivate(conn) # returns a deferred, but it isn't used
        else:
            self.scheduler.scheduleCall(connection_id, conn.start_time, self._doActivate, conn)
            td = conn.start_time - now
            log.msg('Connection %s: activate scheduled for %s UTC (%i seconds) (provision)' % \
                    (conn.connection_id, conn.start_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)

        yield state.provisioned(conn)
        self.logStateUpdate(conn, 'PROVISIONED')

        self.parent_requester.provisionConfirmed(header, connection_id)

        defer.returnValue(conn.connection_id)


    @defer.inlineCallbacks
    def release(self, header, connection_id, request_info=None):

        log.msg('Release request from %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=self.log_system)

        conn = yield self._getConnection(connection_id, header.requester_nsa)
        self._authorize(conn.source_port, conn.dest_port, header, request_info)

        if conn.lifecycle_state in (state.TERMINATING, state.TERMINATED):
            raise error.ConnectionGoneError('Connection %s has been terminated')

        yield state.releasing(conn)
        self.logStateUpdate(conn, 'RELEASING')

        self.scheduler.cancelCall(connection_id)

        if conn.data_plane_active:
            try:
                yield self._doTeardown(conn) # we don't have to block here
            except Exception as e:
                log.msg('Connection %s: Error tearing down link: %s' % (conn.connection_id, e))

        if conn.end_time is not None:
            self.scheduler.scheduleCall(connection_id, conn.end_time, self._doEndtime, conn)
            td = conn.end_time - datetime.datetime.utcnow()
            log.msg('Connection %s: terminate scheduled for %s UTC (%i seconds)' % (conn.connection_id, conn.end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)

        yield state.released(conn)
        self.logStateUpdate(conn, 'RELEASED')

        self.parent_requester.releaseConfirmed(header, connection_id)

        defer.returnValue(conn.connection_id)


    @defer.inlineCallbacks
    def terminate(self, header, connection_id, request_info=None):
        # return defer.fail( error.InternalNRMError('test termination failure') )

        log.msg('Terminate request from %s. Connection ID: %s' % (header.requester_nsa, connection_id), system=self.log_system)

        conn = yield self._getConnection(connection_id, header.requester_nsa)
        self._authorize(conn.source_port, conn.dest_port, header, request_info)

        if conn.lifecycle_state == state.TERMINATED:
            defer.returnValue(conn.cid)

        self.scheduler.cancelCall(conn.connection_id) # cancel end time tear down

        # if we passed end time, resources have already been freed
        free_resources = True
        if conn.lifecycle_state == state.PASSED_ENDTIME:
            free_resources = False

        yield state.terminating(conn)
        self.logStateUpdate(conn, 'TERMINATING')

        if free_resources:
            yield self._doFreeResource(conn)

        # here the reply will practially always come before the ack
        header = nsa.NSIHeader(conn.requester_nsa, conn.requester_nsa) # The NSA is both requester and provider in the backend, but this might be problematic without aggregator
        yield self.parent_requester.terminateConfirmed(header, conn.connection_id)

        yield state.terminated(conn)
        self.logStateUpdate(conn, 'TERMINATED')



    @defer.inlineCallbacks
    def querySummary(self, header, connection_ids=None, global_reservation_ids=None, request_info=None):

        reservations = yield self._query(header, connection_ids, global_reservation_ids)
        self.parent_requester.querySummaryConfirmed(header, reservations)


    @defer.inlineCallbacks
    def queryRecursive(self, header, connection_ids, global_reservation_ids, request_info=None):

        reservations = yield self._query(header, connection_ids, global_reservation_ids)
        self.parent_requester.queryRecursiveConfirmed(header, reservations)


    @defer.inlineCallbacks
    def _query(self, header, connection_ids, global_reservation_ids, request_info=None):
        # generic query mechanism for summary and recursive

        # TODO: Match stps/ports that can be used with credentials and return connections using these STPs
        if connection_ids:
            conns = yield GenericBackendConnections.find(where=['requester_nsa = ? AND connection_id IN ?', header.requester_nsa, tuple(connection_ids) ])
        elif global_reservation_ids:
            conns = yield GenericBackendConnections.find(where=['requester_nsa = ? AND global_reservation_ids IN ?', header.requester_nsa, tuple(global_reservation_ids) ])
        else:
            raise error.MissingParameterError('Must specify connectionId or globalReservationId')

        reservations = []
        for c in conns:
            source_stp = nsa.STP(c.source_network, c.source_port, c.source_label)
            dest_stp   = nsa.STP(c.dest_network, c.dest_port, c.dest_label)
            schedule   = nsa.Schedule(c.start_time, c.end_time)
            sd         = nsa.Point2PointService(source_stp, dest_stp, c.bandwidth, cnt.BIDIRECTIONAL, False, None)
            criteria   = nsa.QueryCriteria(c.revision, schedule, sd)
            data_plane_status = ( c.data_plane_active, c.revision, True )
            states = (c.reservation_state, c.provision_state, c.lifecycle_state, data_plane_status)
            notification_id = self.getNotificationId()
            result_id = notification_id # whatever
            provider_nsa = cnt.URN_OGF_PREFIX + self.network.replace('topology', 'nsa') # hack on
            reservations.append( nsa.ConnectionInfo(c.connection_id, c.global_reservation_id, c.description, cnt.EVTS_AGOLE, [ criteria ],
                                                    provider_nsa, c.requester_nsa, states, notification_id, result_id) )

        defer.returnValue(reservations)


    @defer.inlineCallbacks
    def queryNotification(self, header, connection_id, start_notification=None, end_notification=None):
        raise NotImplementedError('QueryNotification not implemented in generic backend.')

    # --

    @defer.inlineCallbacks
    def _doReserve(self, conn, correlation_id):

        # we have already checked resource availability, so can progress directly through checking
        yield state.reserveMultiSwitch(conn, state.RESERVE_CHECKING, state.RESERVE_HELD)
        self.logStateUpdate(conn, 'RESERVE CHECKING/HELD')

        # schedule 2PC timeout
        if self.scheduler.hasScheduledCall(conn.connection_id):
            # this means that the build scheduler made a call while we yielded
            self.scheduler.cancelCall(conn.connection_id)

        abort_timestamp = datetime.datetime.utcnow() + datetime.timedelta(seconds=self.TPC_TIMEOUT)
        timeout_time = min(abort_timestamp, conn.end_time or abort_timestamp)

        self.scheduler.scheduleCall(conn.connection_id, timeout_time, self._doReserveTimeout, conn)
        td = timeout_time - datetime.datetime.utcnow()
        log.msg('Connection %s: reserve abort scheduled for %s UTC (%i seconds)' % (conn.connection_id, timeout_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)

        schedule = nsa.Schedule(conn.start_time, conn.end_time)
        sc_source_stp = nsa.STP(conn.source_network, conn.source_port, conn.source_label)
        sc_dest_stp   = nsa.STP(conn.dest_network,   conn.dest_port,   conn.dest_label)
        sd = nsa.Point2PointService(sc_source_stp, sc_dest_stp, conn.bandwidth, cnt.BIDIRECTIONAL, False, None) # we fake some things due to db limitations
        crit = nsa.Criteria(conn.revision, schedule, sd)

        header = nsa.NSIHeader(conn.requester_nsa, conn.requester_nsa, correlation_id=correlation_id) # The NSA is both requester and provider in the backend, but this might be problematic without aggregator
        yield self.parent_requester.reserveConfirmed(header, conn.connection_id, conn.global_reservation_id, conn.description, crit)


    @defer.inlineCallbacks
    def _doReserveTimeout(self, conn):

        try:
            yield state.reserveTimeout(conn)
            self.logStateUpdate(conn, 'RESERVE TIMEOUT')

            yield self._doReserveRollback(conn)

            header = nsa.NSIHeader(conn.requester_nsa, conn.requester_nsa) # The NSA is both requester and provider in the backend, but this might be problematic without aggregator
            now = datetime.datetime.utcnow()
            # the conn.requester_nsa is somewhat problematic - the backend should really know its identity
            self.parent_requester.reserveTimeout(header, conn.connection_id, self.getNotificationId(), now, self.TPC_TIMEOUT, conn.connection_id, conn.requester_nsa)

        except Exception as e:
            log.msg('Error in reserveTimeout: %s: %s' % (type(e), e), system=self.log_system)
            log.err(e)


    @defer.inlineCallbacks
    def _doReserveRollback(self, conn):

        try:
            yield state.reserveAbort(conn)
            self.logStateUpdate(conn, 'RESERVE ABORTING')

            self.scheduler.cancelCall(conn.connection_id) # we only have this for non-timeout calls, but just cancel

            # release the resources
            src_resource = self.connection_manager.getResource(conn.source_port, conn.source_label)
            dst_resource = self.connection_manager.getResource(conn.dest_port,   conn.dest_label)

            self.calendar.removeReservation(src_resource, conn.start_time, conn.end_time)
            self.calendar.removeReservation(dst_resource, conn.start_time, conn.end_time)

            yield state.reserved(conn) # we only log this, when we haven't passed end time, as it looks wonky with start+end together

            now = datetime.datetime.utcnow()
            if conn.end_time is not None and now > conn.end_time:
                print('abort do endtime')
                yield self._doEndtime(conn)
            elif conn.end_time is not None:
                self.logStateUpdate(conn, 'RESERVE START')
                self.scheduler.scheduleCall(conn.connection_id, conn.end_time, self._doEndtime, conn)
                td = conn.end_time - datetime.datetime.utcnow()
                log.msg('Connection %s: terminate scheduled for %s UTC (%i seconds)' % (conn.connection_id, conn.end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)

        except Exception as e:
            log.msg('Error in doReserveRollback: %s: %s' % (type(e), e), system=self.log_system)
            log.err(e)


    @defer.inlineCallbacks
    def _doActivate(self, conn):

        src_target = self.connection_manager.getTarget(conn.source_port, conn.source_label)
        dst_target = self.connection_manager.getTarget(conn.dest_port,   conn.dest_label)
        try:
            log.msg('Connection %s: Activating data plane...' % conn.connection_id, system=self.log_system)
            yield self.connection_manager.setupLink(conn.connection_id, src_target, dst_target, conn.bandwidth)
        except Exception as e:
            # We need to mark failure in state machine here somehow....
            #log.err(e) # note: this causes error in tests
            log.msg('Connection %s: Error activating data plane: %s' % (conn.connection_id, str(e)), system=self.log_system)
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
            if end_time is not None and end_time < now:
                log.msg('Connection %s: passed end time during activation, scheduling immediate teardown.' % conn.connection_id, system=self.log_system)
                end_time = now

            if end_time is not None:
                self.scheduler.scheduleCall(conn.connection_id, end_time, self._doEndtime, conn)
                td = end_time - datetime.datetime.utcnow()
                log.msg('Connection %s: End and teardown scheduled for %s UTC (%i seconds)' % (conn.connection_id, end_time.replace(microsecond=0), td.total_seconds()), system=self.log_system)

            data_plane_status = (True, conn.revision, True) # active, version, consistent
            now = datetime.datetime.utcnow()
            header = nsa.NSIHeader(conn.requester_nsa, conn.requester_nsa) # The NSA is both requester and provider in the backend, but this might be problematic without aggregator
            self.parent_requester.dataPlaneStateChange(header, conn.connection_id, self.getNotificationId(), now, data_plane_status)
        except Exception as e:
            log.msg('Error in post-activation: %s: %s' % (type(e), e), system=self.log_system)
            log.err(e)


    @defer.inlineCallbacks
    def _doTeardown(self, conn):
        # this one is not used as a stand-alone, just a utility function

        src_target = self.connection_manager.getTarget(conn.source_port, conn.source_label)
        dst_target = self.connection_manager.getTarget(conn.dest_port,   conn.dest_label)
        try:
            log.msg('Connection %s: Deactivating data plane...' % conn.connection_id, system=self.log_system)
            yield self.connection_manager.teardownLink(conn.connection_id, src_target, dst_target, conn.bandwidth)
        except Exception as e:
            # We need to mark failure in state machine here somehow....
            log.msg('Connection %s: Error deactivating data plane: %s' % (conn.connection_id, str(e)), system=self.log_system)
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
            log.err(e)


    @defer.inlineCallbacks
    def _doEndtime(self, conn):

        if conn.lifecycle_state != state.CREATED:
            raise error.InvalidTransitionError('Cannot end connection in state: %s' % conn.lifecycle_state)

        self.scheduler.cancelCall(conn.connection_id) # not sure about this one, there might some cases though

        yield state.passedEndtime(conn)
        self.logStateUpdate(conn, 'PASSED END TIME')
        yield self._doFreeResource(conn)


    @defer.inlineCallbacks
    def _doFreeResource(self, conn):

        if conn.data_plane_active:
            try:
                yield self._doTeardown(conn)
                # we can only remove resource reservation entry if we succesfully shut down the link :-(
                src_resource = self.connection_manager.getResource(conn.source_port, conn.source_label)
                dst_resource = self.connection_manager.getResource(conn.dest_port,   conn.dest_label)
                self.calendar.removeReservation(src_resource, conn.start_time, conn.end_time)
                self.calendar.removeReservation(dst_resource, conn.start_time, conn.end_time)
            except Exception as e:
                log.msg('Error ending connection: %s' % e)
                raise e
        elif conn.allocated or conn.reservation_state == state.RESERVE_HELD: # free reservation if it was allocated/held
            src_resource = self.connection_manager.getResource(conn.source_port, conn.source_label)
            dst_resource = self.connection_manager.getResource(conn.dest_port,   conn.dest_label)
            self.calendar.removeReservation(src_resource, conn.start_time, conn.end_time)
            self.calendar.removeReservation(dst_resource, conn.start_time, conn.end_time)

