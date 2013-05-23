import os, time, datetime, json, StringIO

from twisted.trial import unittest
from twisted.internet import defer, task

from dateutil.tz import tzutc

from opennsa import nsa, registry, database, error, state, aggregator
from opennsa.topology import nml, nrmparser
from opennsa.backends import dud

from . import topology



class AggregatorTest(unittest.TestCase):

    network = 'Aruba'
    aggregator_system = 'aggregator'

    def setUp(self):

        tcf = os.path.expanduser('~/.opennsa-test.json')
        tc = json.load( open(tcf) )
        database.setupDatabase( tc['database'], tc['database-user'], tc['database-password'])

        self.clock = task.Clock()

        self.sr = registry.ServiceRegistry()
        self.registry_system = 'test-system'

        self.backend = dud.DUDNSIBackend(self.network, self.sr, registry.NSI2_AGGREGATOR)
        self.backend.scheduler.clock = self.clock

        ns_agent = nsa.NetworkServiceAgent('aruba', 'http://localhost:9080/NSI/CS2')

        self.topology = nml.Topology()

        aruba_topo, pim = nrmparser.parseTopologySpec(StringIO.StringIO(topology.ARUBA_TOPOLOGY), self.network, ns_agent)

        self.topology.addNetwork(aruba_topo)

        self.aggregator = aggregator.Aggregator(self.network, ns_agent, self.topology, self.sr, self.registry_system)


        self.backend.startService()

        # stuff to test with
        self.provider_nsa   = nsa.NetworkServiceAgent('testnsa', 'http://example.org/nsa_test_provider')

        src_stp = nsa.STP('Aruba', 'ps',  labels=[ nsa.Label(nml.ETHERNET_VLAN, '1-2') ] )
        dst_stp = nsa.STP('Aruba', 'bon', labels=[ nsa.Label(nml.ETHERNET_VLAN, '2-3') ] )

        start_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=2)
        end_time   = datetime.datetime.utcnow() + datetime.timedelta(seconds=10)
        bandwidth = 200
        self.service_params = nsa.ServiceParameters(start_time, end_time, src_stp, dst_stp, bandwidth)

        self.requester_nsa = nsa.NetworkServiceAgent('test_requester', 'http::/example.org/nsa_test_requester')

        # just so we don't have to put them in the test code
        self.reserve        = self.sr.getHandler(registry.RESERVE,        registry.NSI2_AGGREGATOR)
        self.reserveCommit  = self.sr.getHandler(registry.RESERVE_COMMIT, registry.NSI2_AGGREGATOR)
        self.reserveAbort   = self.sr.getHandler(registry.RESERVE_ABORT,  registry.NSI2_AGGREGATOR)
        self.provision      = self.sr.getHandler(registry.PROVISION,      registry.NSI2_AGGREGATOR)
        self.release        = self.sr.getHandler(registry.RELEASE,        registry.NSI2_AGGREGATOR)
        self.terminate      = self.sr.getHandler(registry.TERMINATE,      registry.NSI2_AGGREGATOR)


    @defer.inlineCallbacks
    def tearDown(self):
        from opennsa.backends.common import simplebackend
        # keep it simple...
        yield simplebackend.Simplebackendconnection.deleteAll()
        yield database.SubConnection.deleteAll()
        yield database.ServiceConnection.deleteAll()

        yield self.backend.stopService()


    @defer.inlineCallbacks
    def testBasicUsage(self):

        cid,_,_,sp = yield self.reserve(self.requester_nsa, self.provider_nsa, None, None, None, None, self.service_params)
        yield self.reserveCommit(self.requester_nsa, self.provider_nsa.urn(), None, cid)
        yield self.terminate(None, self.provider_nsa.urn(), None, cid)


    @defer.inlineCallbacks
    def testProvisionPostTerminate(self):

        cid,__,_,_ = yield self.reserve(self.requester_nsa, self.provider_nsa, None, None, None, None, self.service_params)
        yield self.reserveCommit(self.requester_nsa, self.provider_nsa, None, cid)
        yield self.terminate(self.requester_nsa, self.provider_nsa, None, cid)
        try:
            yield self.provision(self.requester_nsa, self.provider_nsa, None, cid)
            self.fail('Should have raised ConnectionGoneError')
        except error.ConnectionGoneError:
            pass # expected


    @defer.inlineCallbacks
    def testProvisionUsage(self):

        cid,_,_,_ = yield self.reserve(self.requester_nsa, self.provider_nsa, None, None, None, None, self.service_params)
        yield self.reserveCommit(self.requester_nsa, self.provider_nsa, None, cid)
        yield self.provision(self.requester_nsa, self.provider_nsa, None, cid)
        yield self.terminate(self.requester_nsa, self.provider_nsa, None, cid)


    @defer.inlineCallbacks
    def testProvisionReleaseUsage(self):

        d_up   = defer.Deferred()
        d_down = defer.Deferred()

        def dataPlaneChange(requester_nsa, provider_nsa, session_security_attr, connection_id, dps, timestamp):
            active, version, version_consistent = dps
            if active:
                d_up.callback(connection_id)
            else:
                d_down.callback(connection_id)

        self.sr.registerEventHandler(registry.DATA_PLANE_CHANGE,  dataPlaneChange, self.registry_system)

        cid,_,_,_ = yield self.reserve(self.requester_nsa, self.provider_nsa, None, None, None, None, self.service_params)

        yield self.reserveCommit(None, self.provider_nsa, None, cid)

        yield self.provision(self.requester_nsa, self.provider_nsa, None, cid)
        self.clock.advance(3)
        yield d_up
        yield self.release(  self.requester_nsa, self.provider_nsa, None, cid)
        yield d_down
        yield self.terminate(self.requester_nsa, self.provider_nsa, None, cid)


    @defer.inlineCallbacks
    def testDoubleReserve(self):

        cid,_,_,_ = yield self.reserve(self.requester_nsa, self.provider_nsa, None, None, None, None, self.service_params)
        try:
            cid,_,_,_ = yield self.reserve(self.requester_nsa, self.provider_nsa, None, None, None, None, self.service_params)
            self.fail('Should have raised STPUnavailableError')
        except error.STPUnavailableError, e:
            pass # expected


    @defer.inlineCallbacks
    def testProvisionNonExistentConnection(self):

        try:
            yield self.provision(None, self.provider_nsa.urn(), None, '1234')
            self.fail('Should have raised ConnectionNonExistentError')
        except error.ConnectionNonExistentError:
            pass # expected


    @defer.inlineCallbacks
    def testActivation(self):

        d_up = defer.Deferred()

        def dataPlaneChange(requester_nsa, provider_nsa, sessesion_security_attrs, connection_id, dps, timestamp):
            active, version, version_consistent = dps
            if active:
                values = connection_id, active, version_consistent, version, timestamp
                d_up.callback(values)

        self.sr.registerEventHandler(registry.DATA_PLANE_CHANGE,  dataPlaneChange, self.registry_system)

        cid,_,_,_ = yield self.reserve(self.requester_nsa, self.provider_nsa, None, None, None, None, self.service_params)
        yield self.reserveCommit(self.requester_nsa, self.provider_nsa, None, cid)
        yield self.provision(self.requester_nsa, self.provider_nsa, None, cid)
        self.clock.advance(3)
        connection_id, active, version_consistent, version, timestamp = yield d_up
        self.failUnlessEqual(cid, connection_id)
        self.failUnlessEqual(active, True)
        self.failUnlessEqual(version_consistent, True)

        #yield self.release(  None, self.provider_nsa.urn(), None, cid)
        yield self.terminate(self.requester_nsa, self.provider_nsa, None, cid)


    @defer.inlineCallbacks
    def testReserveAbort(self):

        # these need to be constructed such that there is only one label option
        source_stp  = nsa.STP('Aruba', 'A1', labels=[ nsa.Label(nml.ETHERNET_VLAN, '2') ] )
        dest_stp    = nsa.STP('Aruba', 'A3', labels=[ nsa.Label(nml.ETHERNET_VLAN, '2') ] )
        start_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
        end_time   = datetime.datetime.utcnow() + datetime.timedelta(seconds=10)
        service_params = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp, 200)

        cid,_,_,_ = yield self.reserve(self.requester_nsa, self.provider_nsa, None, None, None, None, self.service_params)
        yield self.reserveAbort(self.requester_nsa, self.provider_nsa.urn(), None, cid)
        # try to reserve the same resources
        _ = yield self.reserve(self.requester_nsa, self.provider_nsa, None, None, None, None, self.service_params)


    @defer.inlineCallbacks
    def testReserveTimeout(self):

        # these need to be constructed such that there is only one label option
        source_stp  = nsa.STP('Aruba', 'A1', labels=[ nsa.Label(nml.ETHERNET_VLAN, '2') ] )
        dest_stp    = nsa.STP('Aruba', 'A3', labels=[ nsa.Label(nml.ETHERNET_VLAN, '2') ] )
        start_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
        end_time   = datetime.datetime.utcnow() + datetime.timedelta(seconds=60)
        service_params = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp, 200)

        d = defer.Deferred()
        def reserveTimeout(requester_nsa, provider_nsa, session_security_attrs, connection_id, connection_states, timeout_value, timestamp):
            values = connection_id, connection_states, timeout_value, timestamp
            d.callback(values)

        self.sr.registerEventHandler(registry.RESERVE_TIMEOUT,  reserveTimeout, self.registry_system)

        cid,_,_,_ = yield self.reserve(self.requester_nsa, self.provider_nsa, None, None, None, None, self.service_params)

        self.clock.advance(dud.DUDNSIBackend.TPC_TIMEOUT + 1)
        connection_id, connection_states, timeout_value, timestamp = yield d
        rsm, psm, lsm, asm = connection_states

        self.failUnlessEquals(connection_id, cid)
        #self.failUnlessEquals(rsm, state.RESERVED) # not sure what the state should be here...

        # try to reserve the same resources
        _,_,cid,sp = yield self.reserve(self.requester_nsa, self.provider_nsa, None, None, None, None, self.service_params)



    @defer.inlineCallbacks
    def testFaultyActivate(self):

        d_err = defer.Deferred()

        def errorEvent(requester_nsa, provider_nsa, session_security_attr, connection_id, event, connection_states, timestamp, info, ex):
            d_err.callback( (event, connection_id, connection_states, timestamp, info, ex) )

        self.sr.registerEventHandler(registry.ERROR_EVENT, errorEvent, self.registry_system)

        # make actication fail via monkey patching
        self.backend.connection_manager.setupLink = \
            lambda src, dst : defer.fail(error.InternalNRMError('Link setup failed'))

        cid,_,_,_ = yield self.reserve(self.requester_nsa, self.provider_nsa, None, None, None, None, self.service_params)
        yield self.reserveCommit(self.requester_nsa, self.provider_nsa, None, cid)
        yield self.provision(self.requester_nsa, self.provider_nsa, None, cid)
        self.clock.advance(3)
        vals = yield d_err

        event, connection_id, connection_states, timestamp, info, ex = vals
        self.failUnlessEquals(event, 'activateFailed')
        self.failUnlessEquals(connection_id, cid)


    @defer.inlineCallbacks
    def testFaultyDeactivate(self):

        d_up  = defer.Deferred()
        d_err = defer.Deferred()

        def dataPlaneChange(requester_nsa, provider_nsa, session_securtiy_attr, connection_id, dps, timestamp):
            active, version, version_consistent = dps
            if active:
                d_up.callback( ( connection_id, active, version_consistent, version, timestamp ) )

        def errorEvent(requester_nsa, provider_nsa, session_securtiy_attr, connection_id, event, connection_states, timestamp, info, ex):
            d_err.callback( (event, connection_id, connection_states, timestamp, info, ex) )

        self.sr.registerEventHandler(registry.DATA_PLANE_CHANGE,  dataPlaneChange, self.registry_system)
        self.sr.registerEventHandler(registry.ERROR_EVENT, errorEvent, self.registry_system)

        # make actication fail via monkey patching
        self.backend.connection_manager.teardownLink = \
            lambda src, dst : defer.fail(error.InternalNRMError('Link teardown failed'))

        cid,_,_,_ = yield self.reserve(self.requester_nsa, self.provider_nsa, None, None, None, None, self.service_params)
        yield self.reserveCommit(self.requester_nsa, self.provider_nsa, None, cid)
        yield self.provision(self.requester_nsa, self.provider_nsa, None, cid)

        self.clock.advance(3)
        yield d_up

        self.clock.advance(11)
        yield d_err

