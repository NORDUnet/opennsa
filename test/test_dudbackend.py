import os, datetime, json

from twisted.trial import unittest
from twisted.internet import reactor, defer, task

from opennsa import nsa, registry, database, error, state
from opennsa.topology import nml
from opennsa.backends import dud

from . import common



class DUDBackendTest(unittest.TestCase):

    source_stp  = nsa.STP('Aruba', 'A1', labels=[ nsa.Label(nml.ETHERNET_VLAN, '1-2') ] )
    dest_stp    = nsa.STP('Aruba', 'A3', labels=[ nsa.Label(nml.ETHERNET_VLAN, '2-3') ] )
    start_time  = datetime.datetime.utcnow() + datetime.timedelta(seconds=2)
    end_time    = datetime.datetime.utcnow() + datetime.timedelta(seconds=10)
    bandwidth   = 200

    header         = nsa.NSIHeader('test-requester', 'test-provider', [])
    service_params = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp, bandwidth)

    def setUp(self):

        self.clock = task.Clock()

        self.requester = common.DUDRequester()

        self.provider = dud.DUDNSIBackend('Test', self.requester)
        self.provider.scheduler.clock = self.clock
        self.provider.startService()

        tcf = os.path.expanduser('~/.opennsa-test.json')
        tc = json.load( open(tcf) )
        database.setupDatabase( tc['database'], tc['database-user'], tc['database-password'])


    @defer.inlineCallbacks
    def tearDown(self):
        from opennsa.backends.common import genericbackend
        yield self.provider.stopService()
        # delete all connections from test database
        yield genericbackend.GenericBackendConnections.deleteAll()


    @defer.inlineCallbacks
    def testBasicUsage(self):

        response_cid = yield self.provider.reserve(self.header, None, None, None, self.service_params)
        header, confirm_cid, gid, desc, criteria = yield self.requester.reserve_defer
        self.failUnlessEquals(response_cid, confirm_cid, 'Connection Id from response and confirmation differs')

        yield self.provider.reserveCommit(header, response_cid)
        yield self.requester.reserve_commit_defer

        yield self.provider.terminate(self.header, response_cid)


    @defer.inlineCallbacks
    def testProvisionPostTerminate(self):

        cid = yield self.provider.reserve(self.header, None, None, None, self.service_params)
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
    def testProvisionUsage(self):

        cid = yield self.provider.reserve(self.header, None, None, None, self.service_params)
        yield self.requester.reserve_defer

        yield self.provider.reserveCommit(self.header, cid)
        yield self.requester.reserve_commit_defer

        yield self.provider.provision(self.header, cid)
        yield self.requester.provision_defer

        yield self.provider.terminate(self.header, cid)
        yield self.requester.terminate_defer


    @defer.inlineCallbacks
    def testProvisionReleaseUsage(self):

        acid = yield self.provider.reserve(self.header, None, None, None, self.service_params)
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
    def testDoubleReserve(self):

        acid = yield self.provider.reserve(self.header, None, None, None, self.service_params)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        self.requester.reserve_defer = defer.Deferred() # new defer for new reserve request
        try:
            acid2 = yield self.provider.reserve(self.header, None, None, None, self.service_params)
            self.fail('Should have raised STPUnavailableError')
        except error.STPUnavailableError:
            pass # we expect this


    @defer.inlineCallbacks
    def testProvisionNonExistentConnection(self):

        try:
            yield self.provider.provision(self.header, '1234')
            self.fail('Should have raised ConnectionNonExistentError')
        except error.ConnectionNonExistentError:
            pass # expected


    @defer.inlineCallbacks
    def testActivation(self):

        acid = yield self.provider.reserve(self.header, None, None, None, self.service_params)
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
        source_stp  = nsa.STP('Aruba', 'A1', labels=[ nsa.Label(nml.ETHERNET_VLAN, '2') ] )
        dest_stp    = nsa.STP('Aruba', 'A3', labels=[ nsa.Label(nml.ETHERNET_VLAN, '2') ] )
        start_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
        end_time   = datetime.datetime.utcnow() + datetime.timedelta(seconds=10)
        service_params = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp, 200)

        acid = yield self.provider.reserve(self.header, None, None, None, service_params)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        yield self.provider.reserveAbort(self.header, acid)
        header, cid = yield self.requester.reserve_abort_defer

        self.requester.reserve_defer = defer.Deferred()

        # try to reserve the same resources
        acid2 = yield self.provider.reserve(self.header, None, None, None, service_params)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer


    @defer.inlineCallbacks
    def testReserveTimeout(self):

        # these need to be constructed such that there is only one label option
        source_stp  = nsa.STP('Aruba', 'A1', labels=[ nsa.Label(nml.ETHERNET_VLAN, '2') ] )
        dest_stp    = nsa.STP('Aruba', 'A3', labels=[ nsa.Label(nml.ETHERNET_VLAN, '2') ] )
        start_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
        end_time   = datetime.datetime.utcnow() + datetime.timedelta(seconds=60)
        service_params = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp, 200)

        acid = yield self.provider.reserve(self.header, None, None, None, service_params)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        self.clock.advance(dud.DUDNSIBackend.TPC_TIMEOUT + 1)

        header, cid, notification_id, timestamp, timeout_value, org_cid, org_nsa = yield self.requester.reserve_timeout_defer

        self.failUnlessEquals(cid, acid)

        self.requester.reserve_defer = defer.Deferred()

        # try to reserve the same resources
        acid2 = yield self.provider.reserve(self.header, None, None, None, service_params)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer


    @defer.inlineCallbacks
    def testSlowActivate(self):
        # key here is that end time is passed when activation is done

        source_stp  = nsa.STP('Aruba', 'A1', labels=[ nsa.Label(nml.ETHERNET_VLAN, '100') ] )
        dest_stp    = nsa.STP('Aruba', 'A3', labels=[ nsa.Label(nml.ETHERNET_VLAN, '100') ] )
        start_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
        end_time   = datetime.datetime.utcnow() + datetime.timedelta(seconds=2)
        service_params = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp, 200)

        def setupLink(connection_id, src, dst, bandwidth):
            d = defer.Deferred()
            reactor.callLater(2, d.callback, None)
            return d

        # make actication fail via monkey patching
        self.provider.connection_manager.setupLink = setupLink

        acid = yield self.provider.reserve(self.header, None, None, None, service_params)
        header, cid, gid, desc, sp = yield self.requester.reserve_defer

        yield self.provider.reserveCommit(self.header, cid)
        yield self.requester.reserve_commit_defer

        yield self.provider.provision(self.header, cid)
        yield self.requester.provision_defer

        self.clock.advance(2)

        header, cid, nid, timestamp, dps = yield self.requester.data_plane_change_defer
        active, version, consistent = dps

        self.failUnlessEqual(cid, acid)
        self.failUnlessEqual(active, True)
        self.failUnlessEqual(consistent, True)

        self.requester.data_plane_change_defer = defer.Deferred()

        self.clock.advance(2)
        header, cid, nid, timestamp, dps = yield self.requester.data_plane_change_defer
        active, version, consistent = dps

        self.failUnlessEqual(cid, acid)
        self.failUnlessEqual(active, False)

        yield self.provider.terminate(self.header, cid)
        yield self.requester.terminate_defer

    testSlowActivate.skip = 'Uses reactor calls and real timings, and is too slow to be a regular test'


    @defer.inlineCallbacks
    def testFaultyActivate(self):

        # make actication fail via monkey patching
        self.provider.connection_manager.setupLink = lambda cid, src, dst, bw : defer.fail(error.InternalNRMError('Link setup failed'))

        acid = yield self.provider.reserve(self.header, None, None, None, self.service_params)
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
        self.provider.connection_manager.teardownLink = lambda cid, src, dst, bw : defer.fail(error.InternalNRMError('Link teardown failed'))

        acid = yield self.provider.reserve(self.header, None, None, None, self.service_params)
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

