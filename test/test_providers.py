import os, datetime, json, StringIO

from twisted.trial import unittest
from twisted.internet import reactor, defer, task

from opennsa import nsa, database, error, aggregator
from opennsa.topology import nml, nrmparser
from opennsa.backends import dud

from . import topology, common



class GenericProviderTest:

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
        source_stp  = nsa.STP('Aruba', self.source_port, labels=[ nsa.Label(nml.ETHERNET_VLAN, '2') ] )
        dest_stp    = nsa.STP('Aruba', self.dest_port,   labels=[ nsa.Label(nml.ETHERNET_VLAN, '2') ] )
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
        source_stp  = nsa.STP('Aruba', self.source_port, labels=[ nsa.Label(nml.ETHERNET_VLAN, '2') ] )
        dest_stp    = nsa.STP('Aruba', self.dest_port,   labels=[ nsa.Label(nml.ETHERNET_VLAN, '2') ] )
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
        self.backend.connection_manager.setupLink = setupLink

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
        self.backend.connection_manager.setupLink = lambda cid, src, dst, bw : defer.fail(error.InternalNRMError('Link setup failed'))

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
        self.backend.connection_manager.teardownLink = lambda cid, src, dst, bw : defer.fail(error.InternalNRMError('Link teardown failed'))

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



class DUDBackendTest(GenericProviderTest, unittest.TestCase):

    source_port = 'A1'
    dest_port   = 'A3'

    source_stp  = nsa.STP('Aruba', source_port, labels=[ nsa.Label(nml.ETHERNET_VLAN, '1-2') ] )
    dest_stp    = nsa.STP('Aruba', dest_port,   labels=[ nsa.Label(nml.ETHERNET_VLAN, '2-3') ] )
    bandwidth   = 200

    header         = nsa.NSIHeader('test-requester', 'test-provider', [])

    def setUp(self):

        self.clock = task.Clock()

        self.requester = common.DUDRequester()

        self.backend = dud.DUDNSIBackend('Test', self.requester)

        self.provider = self.backend
        self.provider.scheduler.clock = self.clock
        self.provider.startService()

        tcf = os.path.expanduser('~/.opennsa-test.json')
        tc = json.load( open(tcf) )
        database.setupDatabase( tc['database'], tc['database-user'], tc['database-password'])

        # request stuff
        start_time  = datetime.datetime.utcnow() + datetime.timedelta(seconds=2)
        end_time    = datetime.datetime.utcnow() + datetime.timedelta(seconds=10)
        self.service_params = nsa.ServiceParameters(start_time, end_time, self.source_stp, self.dest_stp, self.bandwidth)


    @defer.inlineCallbacks
    def tearDown(self):
        from opennsa.backends.common import genericbackend
        yield self.provider.stopService()
        # delete all connections from test database
        yield genericbackend.GenericBackendConnections.deleteAll()



class AggregatorTest(GenericProviderTest, unittest.TestCase):

    network = 'Aruba'

    source_port = 'ps'
    dest_port   = 'bon'

    src_stp = nsa.STP('Aruba', 'ps',  labels=[ nsa.Label(nml.ETHERNET_VLAN, '1-2') ] )
    dst_stp = nsa.STP('Aruba', 'bon', labels=[ nsa.Label(nml.ETHERNET_VLAN, '2-3') ] )
    bandwidth = 200

    header         = nsa.NSIHeader('test-requester', 'test-provider', [])

    def setUp(self):

        tcf = os.path.expanduser('~/.opennsa-test.json')
        tc = json.load( open(tcf) )
        database.setupDatabase( tc['database'], tc['database-user'], tc['database-password'])

        self.requester = common.DUDRequester()

        self.clock = task.Clock()

        self.backend = dud.DUDNSIBackend(self.network, None) # we the parent later
        self.backend.scheduler.clock = self.clock

        ns_agent = nsa.NetworkServiceAgent('aruba', 'http://localhost:9080/NSI/CS2')

        aruba_topo, pim = nrmparser.parseTopologySpec(StringIO.StringIO(topology.ARUBA_TOPOLOGY), self.network, ns_agent)
        self.topology = nml.Topology()
        self.topology.addNetwork(aruba_topo)

        providers = { ns_agent.urn() : self.backend }
        self.provider = aggregator.Aggregator(self.network, ns_agent, self.topology, self.requester, providers)

        # set parent for backend, we need to create the aggregator before this can be done
        self.backend.parent_requester = self.provider
        self.backend.startService()

        # request stuff
        start_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=2)
        end_time   = datetime.datetime.utcnow() + datetime.timedelta(seconds=10)

        self.service_params = nsa.ServiceParameters(start_time, end_time, self.src_stp, self.dst_stp, self.bandwidth)


    @defer.inlineCallbacks
    def tearDown(self):
        from opennsa.backends.common import genericbackend
        # keep it simple...
        yield genericbackend.GenericBackendConnections.deleteAll()
        yield database.SubConnection.deleteAll()
        yield database.ServiceConnection.deleteAll()



class RemoteProviderTest(GenericProviderTest, unittest.TestCase):

    PROVIDER_PORT = 8180
    REQUESTER_PORT = 8280

    network = 'Aruba'

    source_port = 'ps'
    dest_port   = 'bon'

    src_stp = nsa.STP('Aruba', 'ps',  labels=[ nsa.Label(nml.ETHERNET_VLAN, '1-2') ] )
    dst_stp = nsa.STP('Aruba', 'bon', labels=[ nsa.Label(nml.ETHERNET_VLAN, '2-3') ] )
    bandwidth = 200

    header         = nsa.NSIHeader('test-requester', 'test-provider', [])

    def setUp(self):
        from dateutil.tz import tzutc
        from twisted.web import resource, server
        from twisted.application import internet
        from opennsa.protocols import nsi2
        from opennsa.protocols.shared import resource as soapresource
        from opennsa.protocols.nsi2 import requesterservice, requesterclient, requester

        tcf = os.path.expanduser('~/.opennsa-test.json')
        tc = json.load( open(tcf) )
        database.setupDatabase( tc['database'], tc['database-user'], tc['database-password'])

        self.requester = common.DUDRequester()

        self.clock = task.Clock()

        self.backend = dud.DUDNSIBackend(self.network, None) # we the parent later
        self.backend.scheduler.clock = self.clock

        ns_agent = nsa.NetworkServiceAgent('aruba', 'http://localhost:%i/NSI/services/CS2' % self.PROVIDER_PORT)

        aruba_topo, pim = nrmparser.parseTopologySpec(StringIO.StringIO(topology.ARUBA_TOPOLOGY), self.network, ns_agent)
        self.topology = nml.Topology()
        self.topology.addNetwork(aruba_topo)

        providers = { ns_agent.urn() : self.backend }
        self.aggregator = aggregator.Aggregator(self.network, ns_agent, self.topology, None, providers) # we set the parent later

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

        providers = {'test-provider' : ns_agent.endpoint }
        requester_url = 'http://localhost:%i/NSI/services/RequesterService2' % self.REQUESTER_PORT
        self.provider = requesterclient.RequesterClient(providers, requester_url)

        requester_service = requesterservice.RequesterService(soap_resource, self.requester) # this is the important part
        requester_factory = server.Site(requester_top_resource, logPath='/dev/null')

        # start engines!
        self.backend.startService()
        self.provider_service.startService()
        self.requester_iport = reactor.listenTCP(self.REQUESTER_PORT, requester_factory)

        # request stuff
        start_time = datetime.datetime.now(tzutc()) + datetime.timedelta(seconds=2)
        end_time   = datetime.datetime.now(tzutc()) + datetime.timedelta(seconds=10)

        self.service_params = nsa.ServiceParameters(start_time, end_time, self.src_stp, self.dst_stp, self.bandwidth)


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

