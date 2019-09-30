import datetime
from io import StringIO

from twisted.trial import unittest
from twisted.internet import reactor, defer, task

from opennsa import nsa, provreg, database, error, setup, aggregator, config, plugin, constants as cnt
from opennsa.topology import nrm
from opennsa.backends import dud

from . import topology, common, db



class GenericProviderTest:

    # basic values we need when testing
    base        = 'aruba'
    network     = base + ':topology'
    source_port = 'ps'
    dest_port   = 'bon'

    source_stp  = nsa.STP(network, source_port, nsa.Label(cnt.ETHERNET_VLAN, '1781-1782') )
    dest_stp    = nsa.STP(network, dest_port,   nsa.Label(cnt.ETHERNET_VLAN, '1782-1783') )
    bandwidth   = 200


    @defer.inlineCallbacks
    def testBasicUsage(self):

        self.header.newCorrelationId()
        response_cid = yield self.provider.reserve(self.header, None, None, None, self.criteria)
        header, confirm_cid, gid, desc, criteria = yield self.requester.reserve_defer
        self.failUnlessEquals(response_cid, confirm_cid, 'Connection Id from response and confirmation differs')

        yield self.provider.reserveCommit(header, response_cid)
        yield self.requester.reserve_commit_defer

        yield self.provider.terminate(self.header, response_cid)


    @defer.inlineCallbacks
    def testProvisionPostTerminate(self):

        self.header.newCorrelationId()
        cid = yield self.provider.reserve(self.header, None, None, None, self.criteria)
        header, confirm_cid, gid, desc, criteria = yield self.requester.reserve_defer

        yield self.provider.reserveCommit(self.header, cid)
        yield self.requester.reserve_commit_defer

        yield self.provider.terminate(self.header, cid)
        yield self.requester.terminate_defer

        try:
            yield self.provider.provision(self.header, cid)
            self.fail('Should have raised ConnectionGoneError')
        except error.ConnectionGoneError:
            pass # expected


    @defer.inlineCallbacks
    def testStartTimeInPast(self):

        start_time = datetime.datetime.utcnow() - datetime.timedelta(seconds=60)
        criteria   = nsa.Criteria(0, nsa.Schedule(start_time, self.end_time), self.sd)

        self.header.newCorrelationId()
        try:
            yield self.provider.reserve(self.header, None, None, None, criteria)
            self.fail('Should have raised PayloadError') # Error type is somewhat debatable, but this what we use
        except error.PayloadError:
            pass # expected


    @defer.inlineCallbacks
    def testNoStartTime(self):

        start_time = None
        criteria   = nsa.Criteria(0, nsa.Schedule(start_time, self.end_time), self.sd)

        self.header.newCorrelationId()
        cid = yield self.provider.reserve(self.header, None, None, None, criteria)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        yield self.provider.reserveCommit(self.header, cid)
        yield self.requester.reserve_commit_defer

        yield self.provider.provision(self.header, cid)
        yield self.requester.provision_defer

        self.clock.advance(3)

        header, cid, nid, timestamp, dps = yield self.requester.data_plane_change_defer
        active, version, consistent = dps
        self.failUnlessEquals(active, True)


    @defer.inlineCallbacks
    def testNoEndTime(self):

        end_time = None
        criteria   = nsa.Criteria(0, nsa.Schedule(self.start_time, end_time), self.sd)

        self.header.newCorrelationId()
        cid = yield self.provider.reserve(self.header, None, None, None, criteria)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        yield self.provider.reserveCommit(self.header, cid)
        yield self.requester.reserve_commit_defer

        yield self.provider.provision(self.header, cid)
        yield self.requester.provision_defer

        self.clock.advance(3)

        header, cid, nid, timestamp, dps = yield self.requester.data_plane_change_defer
        active, version, consistent = dps
        self.failUnlessEquals(active, True)


    @defer.inlineCallbacks
    def testNoStartOrEndTime(self):

        criteria   = nsa.Criteria(0, nsa.Schedule(None, None), self.sd)

        self.header.newCorrelationId()
        cid = yield self.provider.reserve(self.header, None, None, None, criteria)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        yield self.provider.reserveCommit(self.header, cid)
        yield self.requester.reserve_commit_defer

        yield self.provider.provision(self.header, cid)
        yield self.requester.provision_defer

        self.clock.advance(3)

        header, cid, nid, timestamp, dps = yield self.requester.data_plane_change_defer
        active, version, consistent = dps
        self.failUnlessEquals(active, True)



    @defer.inlineCallbacks
    def testHairpinConnection(self):

        source_stp = nsa.STP(self.network, self.source_port, nsa.Label(cnt.ETHERNET_VLAN, '1782') )
        dest_stp = nsa.STP(self.network, self.source_port, nsa.Label(cnt.ETHERNET_VLAN, '1783') )
        sd = nsa.Point2PointService(source_stp, dest_stp, self.bandwidth, cnt.BIDIRECTIONAL, False, None)
        criteria = nsa.Criteria(0, self.schedule, sd)

        self.header.newCorrelationId()
        try:
            yield self.provider.reserve(self.header, None, None, None, criteria)
            self.fail('Should have raised ServceError / TopologyError')
        except error.ServiceError:
            pass # expected - hairpin
        except error.TopologyError:
            pass # expected - double vlan assignment


    @defer.inlineCallbacks
    def testProvisionWithoutCommit(self):

        self.header.newCorrelationId()
        cid = yield self.provider.reserve(self.header, None, None, None, self.criteria)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        self.clock.advance(self.backend.TPC_TIMEOUT + 1)
        header, cid, notification_id, timestamp, timeout_value, org_cid, org_nsa = yield self.requester.reserve_timeout_defer

        try:
            # provision without committing first...
            yield self.provider.provision(self.header, cid)
        except error.ConnectionError:
            pass # expected


    @defer.inlineCallbacks
    def testProvisionUsage(self):

        self.header.newCorrelationId()
        cid = yield self.provider.reserve(self.header, None, None, None, self.criteria)
        yield self.requester.reserve_defer

        yield self.provider.reserveCommit(self.header, cid)
        yield self.requester.reserve_commit_defer

        yield self.provider.provision(self.header, cid)
        yield self.requester.provision_defer

        yield self.provider.terminate(self.header, cid)
        yield self.requester.terminate_defer


    @defer.inlineCallbacks
    def testProvisionReleaseNoStartEndTime(self):

        schedule    = nsa.Schedule(None, None)
        criteria    = nsa.Criteria(0, schedule, nsa.Point2PointService(self.source_stp, self.dest_stp, 200, 'Bidirectional', False, None) )

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, None, None, criteria)
        yield self.requester.reserve_defer

        yield self.provider.reserveCommit(self.header, acid)
        yield self.requester.reserve_commit_defer

        yield self.provider.provision(self.header, acid)
        yield self.requester.provision_defer

        self.clock.advance(3)

        header, cid, nid, timestamp, dps = yield self.requester.data_plane_change_defer
        active, version, consistent = dps
        self.failUnlessEquals(active, True)

        self.requester.data_plane_change_defer = defer.Deferred()

        yield self.provider.release(self.header, acid)
        yield self.requester.release_defer

        header, cid, nid, timestamp, dps = yield self.requester.data_plane_change_defer
        active, version, consistent = dps
        self.failUnlessEquals(active, False)

        yield self.provider.terminate(self.header, cid)
        yield self.requester.terminate_defer


    @defer.inlineCallbacks
    def testProvisionReleaseUsage(self):

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, None, None, self.criteria)
        yield self.requester.reserve_defer

        yield self.provider.reserveCommit(self.header, acid)
        yield self.requester.reserve_commit_defer

        yield self.provider.provision(self.header, acid)
        yield self.requester.provision_defer

        self.clock.advance(3)

        header, cid, nid, timestamp, dps = yield self.requester.data_plane_change_defer
        active, version, consistent = dps
        self.failUnlessEquals(active, True)

        self.requester.data_plane_change_defer = defer.Deferred()

        yield self.provider.release(self.header, acid)
        yield self.requester.release_defer

        header, cid, nid, timestamp, dps = yield self.requester.data_plane_change_defer
        active, version, consistent = dps
        self.failUnlessEquals(active, False)

        yield self.provider.terminate(self.header, cid)
        yield self.requester.terminate_defer


    @defer.inlineCallbacks
    def testInvalidNetworkReservation(self):

        source_stp  = nsa.STP(self.network, self.source_port, nsa.Label(cnt.ETHERNET_VLAN, '1782') )
        dest_stp    = nsa.STP('NoSuchNetwork:topology', 'whatever', nsa.Label(cnt.ETHERNET_VLAN, '1782') )
        criteria    = nsa.Criteria(0, self.schedule, nsa.Point2PointService(source_stp, dest_stp, 200, 'Bidirectional', False, None) )

        self.header.newCorrelationId()
        try:
            yield self.provider.reserve(self.header, None, None, None, criteria)
            self.fail('Should have raised TopologyError')
        except (error.ConnectionCreateError, error.STPResolutionError):
            # we raise ConnectionCreateError in backends, and STPResolutionError in aggregator
            pass # expected


    @defer.inlineCallbacks
    def testLabelRangeMultiReservation(self):

        source_stp  = nsa.STP(self.network, self.source_port, nsa.Label(cnt.ETHERNET_VLAN, '1781-1783') )
        dest_stp    = nsa.STP(self.network, self.dest_port,   nsa.Label(cnt.ETHERNET_VLAN, '1781-1783') )
        criteria    = nsa.Criteria(0, self.schedule, nsa.Point2PointService(source_stp, dest_stp, 100, 'Bidirectional', False, None) )

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, None, None, criteria)
        yield self.requester.reserve_defer

        self.header.newCorrelationId()
        yield self.provider.reserveCommit(self.header, acid)
        yield self.requester.reserve_commit_defer

        self.requester.reserve_defer        = defer.Deferred()
        self.requester.reserve_commit_defer = defer.Deferred()

        self.header.newCorrelationId()
        acid2 = yield self.provider.reserve(self.header, None, None, None, criteria)
        yield self.requester.reserve_defer

        self.header.newCorrelationId()
        yield self.provider.reserveCommit(self.header, acid2)
        yield self.requester.reserve_commit_defer


    @defer.inlineCallbacks
    def testDoubleReserve(self):

        source_stp  = nsa.STP(self.network, self.source_port, nsa.Label(cnt.ETHERNET_VLAN, '1781') )
        p2p = nsa.Point2PointService(source_stp, self.dest_stp, self.bandwidth, cnt.BIDIRECTIONAL, False, None)
        criteria = nsa.Criteria(0, self.schedule, p2p)

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, None, None, criteria)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        self.requester.reserve_defer = defer.Deferred() # new defer for new reserve request
        try:
            acid2 = yield self.provider.reserve(self.header, None, None, None, criteria)
            self.fail('Should have raised STPUnavailableError')
        except error.STPUnavailableError:
            pass # we expect this


    @defer.inlineCallbacks
    def testProvisionNonExistentConnection(self):

        self.header.newCorrelationId()
        try:
            yield self.provider.provision(self.header, '1234')
            self.fail('Should have raised ConnectionNonExistentError')
        except error.ConnectionNonExistentError:
            pass # expected


    @defer.inlineCallbacks
    def testQuerySummary(self):

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, 'gid-123', 'desc2', self.criteria)
        yield self.requester.reserve_defer

        yield self.provider.reserveCommit(self.header, acid)
        yield self.requester.reserve_commit_defer

        self.header.newCorrelationId()
        yield self.provider.querySummary(self.header, connection_ids = [ acid ] )
        header, reservations = yield self.requester.query_summary_defer

        self.failUnlessEquals(len(reservations), 1)
        ci = reservations[0]

        self.failUnlessEquals(ci.connection_id, acid)
        self.failUnlessEquals(ci.global_reservation_id, 'gid-123')
        self.failUnlessEquals(ci.description, 'desc2')

        self.failUnlessEquals(ci.requester_nsa, self.requester_agent.urn())
        self.failUnlessEquals(len(ci.criterias), 1)
        crit = ci.criterias[0]

        src_stp = crit.service_def.source_stp
        dst_stp = crit.service_def.dest_stp

        self.failUnlessEquals(src_stp.network, self.network)
        self.failUnlessEquals(src_stp.port,    self.source_port)
        self.failUnlessEquals(src_stp.label.type_, cnt.ETHERNET_VLAN)
        self.failUnlessIn(src_stp.label.labelValue(), ('1781', '1782') )

        self.failUnlessEquals(dst_stp.network, self.network)
        self.failUnlessEquals(dst_stp.port,    self.dest_port)
        self.failUnlessEquals(dst_stp.label.type_, cnt.ETHERNET_VLAN)
        self.failUnlessIn(dst_stp.label.labelValue(), ('1782', '1783') )

        self.failUnlessEqual(crit.service_def.capacity, self.bandwidth)
        self.failUnlessEqual(crit.revision,   0)

        from opennsa import state
        rsm, psm, lsm, dps = ci.states
        self.failUnlessEquals(rsm, state.RESERVE_START)
        self.failUnlessEquals(psm, state.RELEASED)
        self.failUnlessEquals(lsm, state.CREATED)
        self.failUnlessEquals(dps[:2], (False, 0) )  # we cannot really expect a consistent result for consistent here


    @defer.inlineCallbacks
    def testActivation(self):

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, None, None, self.criteria)
        header, cid, gid, desc, sc = yield self.requester.reserve_defer
        self.failUnlessEqual(cid, acid)

        yield self.provider.reserveCommit(self.header, acid)
        cid = yield self.requester.reserve_commit_defer

        yield self.provider.provision(self.header, acid)
        cid = yield self.requester.provision_defer

        self.clock.advance(3)

        header, cid, nid, timestamp, dps = yield self.requester.data_plane_change_defer
        active, version, consistent = dps

        self.requester.data_plane_change_defer = defer.Deferred() # need a new one for deactivate

        self.failUnlessEqual(cid, acid)
        self.failUnlessEqual(active, True)
        self.failUnlessEqual(consistent, True)

        #yield self.provider.release(self.header, cid)
        #cid = yield self.requester.release_defer

        yield self.provider.terminate(self.header, acid)
        cid = yield self.requester.terminate_defer


    @defer.inlineCallbacks
    def testReserveAbort(self):

        # these need to be constructed such that there is only one label option
        source_stp  = nsa.STP(self.network, self.source_port, nsa.Label(cnt.ETHERNET_VLAN, '1782') )
        dest_stp    = nsa.STP(self.network, self.dest_port,   nsa.Label(cnt.ETHERNET_VLAN, '1782') )
        criteria    = nsa.Criteria(0, self.schedule, nsa.Point2PointService(source_stp, dest_stp, 200, cnt.BIDIRECTIONAL, False, None) )

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, None, None, criteria)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        yield self.provider.reserveAbort(self.header, acid)
        header, cid = yield self.requester.reserve_abort_defer

        self.requester.reserve_defer = defer.Deferred()

        # try to reserve the same resources
        acid2 = yield self.provider.reserve(self.header, None, None, None, criteria)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer


    @defer.inlineCallbacks
    def testNoEndtimeAbort(self):

        # these need to be constructed such that there is only one label option
        source_stp  = nsa.STP(self.network, self.source_port, nsa.Label(cnt.ETHERNET_VLAN, '1782') )
        dest_stp    = nsa.STP(self.network, self.dest_port,   nsa.Label(cnt.ETHERNET_VLAN, '1782') )
        end_time    = None
        criteria    = nsa.Criteria(0, nsa.Schedule(self.start_time, end_time), nsa.Point2PointService(source_stp, dest_stp, 200, cnt.BIDIRECTIONAL, False, None) )

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, None, None, criteria)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        yield self.provider.reserveAbort(self.header, acid)
        header, cid = yield self.requester.reserve_abort_defer

        self.requester.reserve_defer = defer.Deferred()

        # try to reserve the same resources
        acid2 = yield self.provider.reserve(self.header, None, None, None, criteria)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer


    @defer.inlineCallbacks
    def testReserveTerminateReReserve(self):

        # Tamas Varga found a bug where calendar isn't probably cleanup up on reserve+terminate
        # This reproduces the the issue

        # these need to be constructed such that there is only one label option
        source_stp  = nsa.STP(self.network, self.source_port, nsa.Label(cnt.ETHERNET_VLAN, '1782') )
        dest_stp    = nsa.STP(self.network, self.dest_port,   nsa.Label(cnt.ETHERNET_VLAN, '1782') )
        criteria    = nsa.Criteria(0, self.schedule, nsa.Point2PointService(source_stp, dest_stp, 200, cnt.BIDIRECTIONAL, False, None) )

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, None, None, criteria)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        # reset deferred for reservation
        self.requester.reserve_defer = defer.Deferred()

        # terminate the connection
        yield self.provider.terminate(self.header, cid)
        yield self.requester.terminate_defer

        # try to reserve the same resources
        acid2 = yield self.provider.reserve(self.header, None, None, None, criteria)
        yield self.requester.reserve_defer


    @defer.inlineCallbacks
    def testReserveFailAndLabelSwapEnabled(self):

        # When you try to reserve a circuit using a labelSwap enabled backend and the dest_stp appers to be in use,
        # the src stp reservation never gets removed from the calendar

        self.assertTrue(self.backend.connection_manager.canSwapLabel(cnt.ETHERNET_VLAN),"DUD is not able to swapLabels")

        # Construct a valid circuit
        source_stp  = nsa.STP(self.network, self.source_port, nsa.Label(cnt.ETHERNET_VLAN, '1782') )
        dest_stp    = nsa.STP(self.network, self.dest_port,   nsa.Label(cnt.ETHERNET_VLAN, '1782') )
        criteria    = nsa.Criteria(0, self.schedule, nsa.Point2PointService(source_stp, dest_stp, 200, cnt.BIDIRECTIONAL, False, None) )

        #We shouldn't have reservations in the calendar right now
        self.assertEquals(len(self.backend.calendar.reservations), 0,
                          "Reservations size is %s should be 0" % len(self.backend.calendar.reservations))

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, None, None, criteria)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        # reset deferred for reservation
        self.requester.reserve_defer = defer.Deferred()

        # 2 reservations, for source_stp and dest_stp
        self.assertEquals(len(self.backend.calendar.reservations), 2,
                          "Reservations size is %s should be 2" % len(self.backend.calendar.reservations))

        #Construct a second circuit, with the same dest_stp
        source_stp2 = nsa.STP(self.network,self.source_port, nsa.Label(cnt.ETHERNET_VLAN, '1781'))
        criteria2    = nsa.Criteria(0, self.schedule, nsa.Point2PointService(source_stp2, dest_stp, 200, cnt.BIDIRECTIONAL, False, None) )

        self.header.newCorrelationId()
        try:
            acid2 = yield self.provider.reserve(self.header, None, None, None, criteria2)
            header2, cid2, gid2, desc2, sp2 = yield self.requester.reserve_defer
        except error.STPUnavailableError as e:
            pass

        # reset deferred for reservation
        self.requester.reserve_defer = defer.Deferred()

        # The second reserve request failed, so we should have the original 2 reservations in the calendar
        self.assertEquals(len(self.backend.calendar.reservations), 2,
                         "Reservations size is %s should be 2" % len(self.backend.calendar.reservations))

        # terminate the connection
        yield self.provider.terminate(self.header, cid)
        yield self.requester.terminate_defer

        for stp in [source_stp2,dest_stp,source_stp]:
            try:
                res = self.backend.connection_manager.getResource(stp.port, stp.label)
                resource_is_available = self.backend.calendar.checkReservation(res, self.schedule.start_time,self.schedule.end_time)
            except error.STPUnavailableError as e:
                self.fail("STP %s should be available" % res)


    @defer.inlineCallbacks
    def testReserveTimeout(self):

        # these need to be constructed such that there is only one label option
        source_stp  = nsa.STP(self.network, self.source_port, nsa.Label(cnt.ETHERNET_VLAN, '1782') )
        dest_stp    = nsa.STP(self.network, self.dest_port,   nsa.Label(cnt.ETHERNET_VLAN, '1782') )
        criteria    = nsa.Criteria(0, self.schedule, nsa.Point2PointService(source_stp, dest_stp, self.bandwidth, cnt.BIDIRECTIONAL, False, None) )

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, None, None, criteria)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        self.clock.advance(self.backend.TPC_TIMEOUT + 1)

        header, cid, notification_id, timestamp, timeout_value, org_cid, org_nsa = yield self.requester.reserve_timeout_defer

        self.failUnlessEquals(cid, acid)

        self.requester.reserve_defer = defer.Deferred()

        # new criteria
        start_time  = datetime.datetime.utcnow() + datetime.timedelta(seconds=2)
        end_time    = datetime.datetime.utcnow() + datetime.timedelta(seconds=6)
        schedule    = nsa.Schedule(start_time, end_time)
        criteria    = nsa.Criteria(0, schedule, nsa.Point2PointService(source_stp, dest_stp, self.bandwidth, cnt.BIDIRECTIONAL, False, None) )

        # try to reserve the same resources
        acid2 = yield self.provider.reserve(self.header, None, None, None, criteria)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer


    @defer.inlineCallbacks
    def testSlowActivate(self):
        # key here is that end time is passed when activation is done

        start_time  = datetime.datetime.utcnow() + datetime.timedelta(seconds=2)
        end_time    = datetime.datetime.utcnow() + datetime.timedelta(seconds=4)
        schedule = nsa.Schedule(start_time, end_time)

        source_stp  = nsa.STP(self.network, self.source_port, nsa.Label(cnt.ETHERNET_VLAN, '1780') )
        dest_stp    = nsa.STP(self.network, self.dest_port,   nsa.Label(cnt.ETHERNET_VLAN, '1780') )
        criteria    = nsa.Criteria(0, schedule, nsa.Point2PointService(source_stp, dest_stp, 200, cnt.BIDIRECTIONAL, False, None) )

        def setupLink(connection_id, src, dst, bandwidth):
            d = defer.Deferred()
            reactor.callLater(2, d.callback, None)
            return d

        # make activation slow via monkey patching
        self.backend.connection_manager.setupLink = setupLink

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, None, None, criteria)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        self.failUnlessEqual(cid, acid)

        yield self.provider.reserveCommit(self.header, cid)
        yield self.requester.reserve_commit_defer

        yield self.provider.provision(self.header, cid)
        yield self.requester.provision_defer

        self.clock.advance(3)

        header, cid, nid, timestamp, dps = yield self.requester.data_plane_change_defer
        active, version, consistent = dps

        self.failUnlessEqual(cid, acid)
        self.failUnlessEqual(active, True)
        self.failUnlessEqual(consistent, True)

        self.requester.data_plane_change_defer = defer.Deferred()

        self.clock.advance(2)
        header, cid, nid, timestamp, dps =  yield self.requester.data_plane_change_defer
        active, version, consistent = dps

        self.failUnlessEqual(cid, acid)
        self.failUnlessEqual(active, False)

        yield self.provider.terminate(self.header, cid)
        yield self.requester.terminate_defer

    testSlowActivate.timeout = 15
    testSlowActivate.skip = 'Too slow to be a regular test (uses reactor calls and real timings)'


    @defer.inlineCallbacks
    def testFaultyActivate(self):

        # make actication fail via monkey patching
        self.backend.connection_manager.setupLink = lambda cid, src, dst, bw : defer.fail(error.InternalNRMError('Link setup failed'))

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, None, None, self.criteria)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        yield self.provider.reserveCommit(self.header, acid)
        header, cid = yield self.requester.reserve_commit_defer

        yield self.provider.provision(self.header, cid)
        header, cid = yield self.requester.provision_defer

        self.clock.advance(3)

        header, cid, nid, timestamp, event, info, ex = yield self.requester.error_event_defer

        self.failUnlessEquals(event, 'activateFailed')
        self.failUnlessEquals(cid, acid)


    @defer.inlineCallbacks
    def testFaultyDeactivate(self):

        # make actication fail via monkey patching
        self.backend.connection_manager.teardownLink = lambda cid, src, dst, bw : defer.fail(error.InternalNRMError('Link teardown failed'))

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, None, None, self.criteria)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        yield self.provider.reserveCommit(self.header, cid)
        header, cid = yield self.requester.reserve_commit_defer

        yield self.provider.provision(self.header, cid)
        header, cid = yield self.requester.provision_defer

        self.clock.advance(3)

        header, cid, nid, timestamp, dps = yield self.requester.data_plane_change_defer
        active, version, consistent = dps
        self.requester.data_plane_change_defer = defer.Deferred()

        self.clock.advance(11)

        header, cid, nid, timestamp, event, info, ex = yield self.requester.error_event_defer
        self.failUnlessEquals(event, 'deactivateFailed')
        self.failUnlessEquals(cid, acid)


    @defer.inlineCallbacks
    def testIdenticalPortSTPs(self):

        source_stp  = nsa.STP(self.network, 'eth1', None)
        dest_stp    = nsa.STP(self.network, 'eth1', None)

        criteria    = nsa.Criteria(0, self.schedule, nsa.Point2PointService(source_stp, dest_stp, 200, cnt.BIDIRECTIONAL, False, None) )

        self.header.newCorrelationId()
        try:
            acid = yield self.provider.reserve(self.header, None, None, None, criteria)
            self.fail("Should have gotten service error for identical ports")
        except error.ServiceError:
            pass # expected


    @defer.inlineCallbacks
    def testInvalidRewrite(self):

        source_stp  = nsa.STP(self.network, 'eth1', None)

        criteria    = nsa.Criteria(0, self.schedule, nsa.Point2PointService(source_stp, self.dest_stp, 200, cnt.BIDIRECTIONAL, False, None) )

        self.header.newCorrelationId()
        try:
            acid = yield self.provider.reserve(self.header, None, None, None, criteria)
            self.fail("Should have gotten topology error ")
        except error.NSIError:
            pass # expected


    @defer.inlineCallbacks
    def testPortSTPs(self):

        source_stp  = nsa.STP(self.network, 'eth1', None)
        dest_stp    = nsa.STP(self.network, 'eth2', None)

        criteria    = nsa.Criteria(0, self.schedule, nsa.Point2PointService(source_stp, dest_stp, 200, cnt.BIDIRECTIONAL, False, None) )

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, None, None, criteria)
        header, cid, gid, desc, sc = yield self.requester.reserve_defer
        self.failUnlessEqual(cid, acid)

        yield self.provider.reserveCommit(self.header, acid)
        cid = yield self.requester.reserve_commit_defer

        yield self.provider.provision(self.header, acid)
        cid = yield self.requester.provision_defer

        self.clock.advance(3)

        header, cid, nid, timestamp, dps = yield self.requester.data_plane_change_defer
        active, version, consistent = dps

        self.requester.data_plane_change_defer = defer.Deferred() # need a new one for deactivate

        self.failUnlessEqual(cid, acid)
        self.failUnlessEqual(active, True)
        self.failUnlessEqual(consistent, True)

        #yield self.provider.release(self.header, cid)
        #cid = yield self.requester.release_defer

        yield self.provider.terminate(self.header, acid)
        cid = yield self.requester.terminate_defer


    @defer.inlineCallbacks
    def testNoStartEndTimeAndAdditionalReservation(self):

        schedule    = nsa.Schedule(None, None)
        criteria    = nsa.Criteria(0, schedule, nsa.Point2PointService(self.source_stp, self.dest_stp, 200, cnt.BIDIRECTIONAL, False, None) )

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, None, None, criteria)
        header, cid, gid, desc, sc = yield self.requester.reserve_defer
        self.failUnlessEqual(cid, acid)

        yield self.provider.reserveCommit(self.header, acid)
        cid = yield self.requester.reserve_commit_defer

        # second reservation
        self.header.newCorrelationId()
        self.requester.reserve_defer = defer.Deferred()
        self.requester.reserve_commit_defer = defer.Deferred()

        schedule    = nsa.Schedule(None, None)
        criteria    = nsa.Criteria(0, schedule, nsa.Point2PointService(self.source_stp, self.dest_stp, 200, cnt.BIDIRECTIONAL, False, None) )

        acid2 = yield self.provider.reserve(header, None, None, None, criteria)
        _ = yield self.requester.reserve_defer

        yield self.provider.reserveCommit(self.header, acid2)
        cid = yield self.requester.reserve_commit_defer



class DUDBackendTest(GenericProviderTest, unittest.TestCase):

    requester_agent = nsa.NetworkServiceAgent('test-requester:nsa', b'dud_endpoint1')
    provider_agent  = nsa.NetworkServiceAgent(GenericProviderTest.base + ':nsa', b'dud_endpoint2')

    header      = nsa.NSIHeader(requester_agent.urn(), provider_agent.urn())

    def setUp(self):

        self.clock = task.Clock()

        self.requester = common.DUDRequester()

        nrm_ports = nrm.parsePortSpec(StringIO(topology.ARUBA_TOPOLOGY))

        self.backend = dud.DUDNSIBackend(self.network, nrm_ports, self.requester, {})

        self.provider = self.backend
        self.provider.scheduler.clock = self.clock
        self.provider.startService()

        db.setupDatabase()

        # request stuff
        self.start_time  = datetime.datetime.utcnow() + datetime.timedelta(seconds=2)
        self.end_time    = datetime.datetime.utcnow() + datetime.timedelta(seconds=10)

        self.schedule = nsa.Schedule(self.start_time, self.end_time)
        self.sd = nsa.Point2PointService(self.source_stp, self.dest_stp, self.bandwidth, cnt.BIDIRECTIONAL, False ,None)
        self.criteria = nsa.Criteria(0, self.schedule, self.sd)

        return self.backend.restore_defer


    @defer.inlineCallbacks
    def tearDown(self):
        from opennsa.backends.common import genericbackend
        yield self.provider.stopService()
        # delete all connections from test database
        yield genericbackend.GenericBackendConnections.deleteAll()

        # close database connections, so we don't run out
        from twistar.registry import Registry
        Registry.DBPOOL.close()

    def testHairpinConnection(self):
        pass
    testHairpinConnection.skip = 'Tested in aggregator'



class AggregatorTest(GenericProviderTest, unittest.TestCase):

    requester_agent = nsa.NetworkServiceAgent('test-requester:nsa', b'dud_endpoint1')
    provider_agent  = nsa.NetworkServiceAgent(GenericProviderTest.base + ':nsa', b'dud_endpoint2')
    header          = nsa.NSIHeader(requester_agent.urn(), provider_agent.urn(), connection_trace= [ requester_agent.urn() + ':1' ],
                                    security_attributes = [ nsa.SecurityAttribute('user', 'testuser') ] )

    def setUp(self):

        db.setupDatabase()

        self.requester = common.DUDRequester()

        self.clock = task.Clock()

        nrm_map = StringIO(topology.ARUBA_TOPOLOGY)
        nrm_ports, nml_network, link_vector = setup.setupTopology(nrm_map, self.network, 'aruba.net')

        self.backend = dud.DUDNSIBackend(self.network, nrm_ports, self.requester, {})
        self.backend.scheduler.clock = self.clock

        pl = plugin.BasePlugin()
        pl.init( { config.NETWORK_NAME: self.network }, None )

        pr = provreg.ProviderRegistry( { self.provider_agent.urn() : self.backend }, {} )
        self.provider = aggregator.Aggregator(self.network, self.provider_agent, nml_network, link_vector, self.requester, pr, [], pl)

        # set parent for backend, we need to create the aggregator before this can be done
        self.backend.parent_requester = self.provider
        self.backend.startService()

        # request stuff
        self.start_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=2)
        self.end_time   = datetime.datetime.utcnow() + datetime.timedelta(seconds=10)

        self.schedule = nsa.Schedule(self.start_time, self.end_time)
        self.sd       = nsa.Point2PointService(self.source_stp, self.dest_stp, self.bandwidth, cnt.BIDIRECTIONAL, False, None)
        self.criteria = nsa.Criteria(0, self.schedule, self.sd)


    @defer.inlineCallbacks
    def tearDown(self):
        from opennsa.backends.common import genericbackend
        # keep it simple...
        yield genericbackend.GenericBackendConnections.deleteAll()
        yield database.SubConnection.deleteAll()
        yield database.ServiceConnection.deleteAll()
        # close database connections, so we don't run out
        from twistar.registry import Registry
        Registry.DBPOOL.close()


    @defer.inlineCallbacks
    def testHairpinConnectionAllowed(self):

        self.provider.policies.append(cnt.ALLOW_HAIRPIN)

        source_stp = nsa.STP(self.network, self.source_port, nsa.Label(cnt.ETHERNET_VLAN, '1782') )
        dest_stp   = nsa.STP(self.network, self.source_port, nsa.Label(cnt.ETHERNET_VLAN, '1783') )
        sd = nsa.Point2PointService(source_stp, dest_stp, self.bandwidth, cnt.BIDIRECTIONAL, False, None)
        criteria = nsa.Criteria(0, self.schedule, sd)

        self.header.newCorrelationId()
        try:
            acid = yield self.provider.reserve(self.header, None, None, None, criteria)
            yield self.requester.reserve_defer
        except Exception as e:
            self.fail('Should not have raised exception: %s' % str(e))



class RemoteProviderTest(GenericProviderTest, unittest.TestCase):

    PROVIDER_PORT = 8180
    REQUESTER_PORT = 8280

    requester_agent = nsa.NetworkServiceAgent('test-requester:nsa', b'http://localhost:%i/NSI/services/RequesterService2' % REQUESTER_PORT)
    provider_agent  = nsa.NetworkServiceAgent(GenericProviderTest.base + ':nsa', b'http://localhost:%i/NSI/services/CS2' % PROVIDER_PORT)
    header   = nsa.NSIHeader(requester_agent.urn(), provider_agent.urn(), reply_to=requester_agent.endpoint, connection_trace=[ requester_agent.urn() + ':1' ],
                             security_attributes = [ nsa.SecurityAttribute('user', 'testuser') ] )

    def setUp(self):
        from twisted.web import resource, server
        from twisted.application import internet
        from opennsa.protocols import nsi2
        from opennsa.protocols.shared import soapresource
        from opennsa.protocols.nsi2 import requesterservice, requesterclient

        db.setupDatabase()

        self.requester = common.DUDRequester()

        self.clock = task.Clock()

        nrm_map = StringIO(topology.ARUBA_TOPOLOGY)
        nrm_ports, nml_network, link_vector = setup.setupTopology(nrm_map, self.network, 'aruba.net')

        self.backend = dud.DUDNSIBackend(self.network, nrm_ports, None, {}) # we set the parent later
        self.backend.scheduler.clock = self.clock

        pl = plugin.BasePlugin()
        pl.init( { config.NETWORK_NAME: self.network }, None )

        pr = provreg.ProviderRegistry( { self.provider_agent.urn() : self.backend }, {} )
        self.aggregator = aggregator.Aggregator(self.network, self.provider_agent, nml_network, link_vector, None, pr, [], pl) # we set the parent later

        self.backend.parent_requester = self.aggregator

        # provider protocol
        http_top_resource = resource.Resource()

        cs2_prov = nsi2.setupProvider(self.aggregator, http_top_resource)
        self.aggregator.parent_requester = cs2_prov

        provider_factory = server.Site(http_top_resource)
        self.provider_service = internet.TCPServer(self.PROVIDER_PORT, provider_factory)

        # requester protocol

        requester_top_resource = resource.Resource()
        soap_resource = soapresource.setupSOAPResource(requester_top_resource, 'RequesterService2')

        self.provider = requesterclient.RequesterClient(self.provider_agent.endpoint, self.requester_agent.endpoint)

        requester_service = requesterservice.RequesterService(soap_resource, self.requester) # this is the important part
        requester_factory = server.Site(requester_top_resource, logPath='/dev/null')

        # start engines!
        self.backend.startService()
        self.provider_service.startService()
        self.requester_iport = reactor.listenTCP(self.REQUESTER_PORT, requester_factory)

        # request stuff
        self.start_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=2)
        self.end_time   = datetime.datetime.utcnow() + datetime.timedelta(seconds=10)

        self.schedule = nsa.Schedule(self.start_time, self.end_time)
        self.sd = nsa.Point2PointService(self.source_stp, self.dest_stp, self.bandwidth)
        self.criteria = nsa.Criteria(0, self.schedule, self.sd)


    @defer.inlineCallbacks
    def tearDown(self):

        self.backend.stopService()
        self.provider_service.stopService()
        self.requester_iport.stopListening()

        from opennsa.backends.common import genericbackend
        # keep it simple...
        yield genericbackend.GenericBackendConnections.deleteAll()
        yield database.SubConnection.deleteAll()
        yield database.ServiceConnection.deleteAll()

        # close database connections, so we don't run out
        from twistar.registry import Registry
        Registry.DBPOOL.close()


    @defer.inlineCallbacks
    def testQuerySummarySync(self):
        # sync is only available remotely

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, 'gid-123', 'desc2', self.criteria)
        yield self.requester.reserve_defer

        yield self.provider.reserveCommit(self.header, acid)
        yield self.requester.reserve_commit_defer

        reservations = yield self.provider.querySummarySync(self.header, connection_ids = [ acid ] )

        self.failUnlessEquals(len(reservations), 1)

        ci = reservations[0]

        self.failUnlessEquals(ci.connection_id, acid)
        self.failUnlessEquals(ci.global_reservation_id, 'gid-123')
        self.failUnlessEquals(ci.description, 'desc2')

        self.failUnlessEquals(ci.requester_nsa, self.requester_agent.urn())
        self.failUnlessEquals(len(ci.criterias), 1)
        crit = ci.criterias[0]
        sd = crit.service_def

        src_stp = sd.source_stp
        dst_stp = sd.dest_stp

        self.failUnlessEquals(src_stp.network, self.network)
        self.failUnlessEquals(src_stp.port,    self.source_port)
        self.failUnlessEquals(src_stp.label.type_, cnt.ETHERNET_VLAN)
        self.failUnlessIn(src_stp.label.labelValue(), ('1781', '1782') )

        self.failUnlessEquals(dst_stp.network, self.network)
        self.failUnlessEquals(dst_stp.port,    self.dest_port)
        self.failUnlessEquals(dst_stp.label.type_, cnt.ETHERNET_VLAN)
        self.failUnlessIn(dst_stp.label.labelValue(), ('1782', '1783') )

        self.failUnlessEqual(sd.capacity, self.bandwidth)
        self.failUnlessEqual(crit.revision,   0)

        from opennsa import state
        rsm, psm, lsm, dps = ci.states
        self.failUnlessEquals(rsm, state.RESERVE_START)
        self.failUnlessEquals(psm, state.RELEASED)
        self.failUnlessEquals(lsm, state.CREATED)
        self.failUnlessEquals(dps[:2], (False, 0) )  # we cannot really expect a consistent result for consistent here


    @defer.inlineCallbacks
    def testQueryRecursive(self):
        # only available on aggregator and remote, we just do remote for now

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, 'gid-123', 'desc2', self.criteria)
        yield self.requester.reserve_defer

        yield self.provider.reserveCommit(self.header, acid)
        yield self.requester.reserve_commit_defer

        self.header.newCorrelationId()
        yield self.provider.queryRecursive(self.header, connection_ids = [ acid ] )
        header, reservations = yield self.requester.query_recursive_defer

        self.failUnlessEquals(len(reservations), 1)
        ci = reservations[0]

        self.failUnlessEquals(ci.connection_id, acid)
        self.failUnlessEquals(ci.global_reservation_id, 'gid-123')
        self.failUnlessEquals(ci.description, 'desc2')

        self.failUnlessEquals(ci.requester_nsa, self.requester_agent.urn())
        self.failUnlessEquals(len(ci.criterias), 1)
        crit = ci.criterias[0]

        src_stp = crit.service_def.source_stp
        dst_stp = crit.service_def.dest_stp

        self.failUnlessEquals(src_stp.network, self.network)
        self.failUnlessEquals(src_stp.port,    self.source_port)
        self.failUnlessEquals(src_stp.label.type_, cnt.ETHERNET_VLAN)
        self.failUnlessIn(src_stp.label.labelValue(), ('1781', '1782') )

        self.failUnlessEquals(dst_stp.network, self.network)
        self.failUnlessEquals(dst_stp.port,    self.dest_port)
        self.failUnlessEquals(dst_stp.label.type_, cnt.ETHERNET_VLAN)
        self.failUnlessIn(dst_stp.label.labelValue(), ('1782', '1783') )

        self.failUnlessEqual(crit.service_def.capacity, self.bandwidth)
        self.failUnlessEqual(crit.revision,   0)

        from opennsa import state
        rsm, psm, lsm, dps = ci.states
        self.failUnlessEquals(rsm, state.RESERVE_START)
        self.failUnlessEquals(psm, state.RELEASED)
        self.failUnlessEquals(lsm, state.CREATED)
        self.failUnlessEquals(dps[:2], (False, 0) )  # we cannot really expect a consistent result for consistent here

        self.failUnlessEqual(len(crit.children), 1)
        child = crit.children[0]

        rsm, psm, lsm, dps = ci.states # overwrite
        self.failUnlessEquals(rsm, state.RESERVE_START)
        self.failUnlessEquals(psm, state.RELEASED)
        self.failUnlessEquals(lsm, state.CREATED)
        self.failUnlessEquals(dps[:2], (False, 0) )  # we cannot really expect a consistent result for consistent here


    @defer.inlineCallbacks
    def testQueryRecursiveNoStartTime(self):
        # only available on aggregator and remote, we just do remote for now

        start_time = None
        criteria   = nsa.Criteria(0, nsa.Schedule(start_time, self.end_time), self.sd)

        self.header.newCorrelationId()
        acid = yield self.provider.reserve(self.header, None, 'gid-123', 'desc2', criteria)
        yield self.requester.reserve_defer

        yield self.provider.reserveCommit(self.header, acid)
        yield self.requester.reserve_commit_defer

        self.header.newCorrelationId()
        yield self.provider.queryRecursive(self.header, connection_ids = [ acid ] )
        header, reservations = yield self.requester.query_recursive_defer

        self.failUnlessEquals(len(reservations), 1)
        ci = reservations[0]

        self.failUnlessEquals(ci.connection_id, acid)
        self.failUnlessEquals(ci.global_reservation_id, 'gid-123')
        self.failUnlessEquals(ci.description, 'desc2')

        self.failUnlessEquals(ci.requester_nsa, self.requester_agent.urn())
        self.failUnlessEquals(len(ci.criterias), 1)
        crit = ci.criterias[0]

        src_stp = crit.service_def.source_stp
        dst_stp = crit.service_def.dest_stp

        self.failUnlessEquals(src_stp.network, self.network)
        self.failUnlessEquals(src_stp.port,    self.source_port)
        self.failUnlessEquals(src_stp.label.type_, cnt.ETHERNET_VLAN)
        self.failUnlessIn(src_stp.label.labelValue(), ('1781', '1782') )

        self.failUnlessEquals(dst_stp.network, self.network)
        self.failUnlessEquals(dst_stp.port,    self.dest_port)
        self.failUnlessEquals(dst_stp.label.type_, cnt.ETHERNET_VLAN)
        self.failUnlessIn(dst_stp.label.labelValue(), ('1782', '1783') )

        self.failUnlessEqual(crit.service_def.capacity, self.bandwidth)
        self.failUnlessEqual(crit.revision,   0)

        from opennsa import state
        rsm, psm, lsm, dps = ci.states
        self.failUnlessEquals(rsm, state.RESERVE_START)
        self.failUnlessEquals(psm, state.RELEASED)
        self.failUnlessEquals(lsm, state.CREATED)
        self.failUnlessEquals(dps[:2], (False, 0) )  # we cannot really expect a consistent result for consistent here

        self.failUnlessEqual(len(crit.children), 1)
        child = crit.children[0]

        rsm, psm, lsm, dps = ci.states # overwrite
        self.failUnlessEquals(rsm, state.RESERVE_START)
        self.failUnlessEquals(psm, state.RELEASED)
        self.failUnlessEquals(lsm, state.CREATED)
        self.failUnlessEquals(dps[:2], (False, 0) )  # we cannot really expect a consistent result for consistent here

