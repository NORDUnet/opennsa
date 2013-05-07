import time, datetime

from twisted.trial import unittest
from twisted.internet import defer

from dateutil.tz import tzutc

from opennsa import nsa, registry, database, error
from opennsa.topology import nml
from opennsa.backends import dud



class DUDBackendTest(unittest.TestCase):

    def setUp(self):

        self.sr = registry.ServiceRegistry()
        self.backend = dud.DUDNSIBackend('Test', self.sr)
        self.backend.startService()

        database.setupDatabase('ontest', 'htj', 'htj')

        self.provider_nsa   = nsa.NetworkServiceAgent('testnsa', 'http://example.org/nsa')

        source_stp  = nsa.STP('Aruba', 'A1', labels=[ nsa.Label(nml.ETHERNET_VLAN, '1-2') ] )
        dest_stp    = nsa.STP('Aruba', 'A3', labels=[ nsa.Label(nml.ETHERNET_VLAN, '2-3') ] )
        start_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=.35)
        end_time   = datetime.datetime.utcnow() + datetime.timedelta(seconds=10)
        bandwidth = 200
        self.service_params = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp, bandwidth)

        # just so we don't have to put them in the test code
        self.reserve        = self.sr.getHandler(registry.RESERVE,        registry.NSI2_LOCAL)
        self.reserveCommit  = self.sr.getHandler(registry.RESERVE_COMMIT, registry.NSI2_LOCAL)
        self.reserveAbort   = self.sr.getHandler(registry.RESERVE_ABORT,  registry.NSI2_LOCAL)
        self.provision      = self.sr.getHandler(registry.PROVISION,      registry.NSI2_LOCAL)
        self.release        = self.sr.getHandler(registry.RELEASE,        registry.NSI2_LOCAL)
        self.terminate      = self.sr.getHandler(registry.TERMINATE,      registry.NSI2_LOCAL)


    def tearDown(self):
        return self.backend.stopService()


    @defer.inlineCallbacks
    def testBasicUsage(self):

        _,_,cid,sp = yield self.reserve(None, self.provider_nsa.urn(), None, None, None, None, self.service_params)
        yield self.terminate(None, self.provider_nsa.urn(), None, cid)


    @defer.inlineCallbacks
    def testProvisionUsage(self):

        _,_,cid,sp = yield self.reserve(None, self.provider_nsa.urn(), None, None, None, None, self.service_params)
        yield self.reserveCommit(None, self.provider_nsa.urn(), None, cid)
        yield self.provision(None, self.provider_nsa.urn(), None, cid)
        yield self.terminate(None, self.provider_nsa.urn(), None, cid)


    @defer.inlineCallbacks
    def testProvisionReleaseUsage(self):

        _,_,cid,sp = yield self.reserve(None, self.provider_nsa.urn(), None, None, None, None, self.service_params)
        yield self.reserveCommit(None, self.provider_nsa.urn(), None, cid)
        yield self.provision(None, self.provider_nsa.urn(), None, cid)
        yield self.release(  None, self.provider_nsa.urn(), None, cid)
        yield self.terminate(None, self.provider_nsa.urn(), None, cid)


    @defer.inlineCallbacks
    def testDoubleReserve(self):

        _ = yield self.reserve(None, self.provider_nsa.urn(), None, None, None, None, self.service_params)
        try:
            _ = yield self.reserve(None, self.provider_nsa.urn(), None, None, None, None, self.service_params)
            self.fail('Should have raised STPUnavailableError')
        except error.STPUnavailableError:
            pass # we expect this


    @defer.inlineCallbacks
    def testProvisionNonExistentConnection(self):

        try:
            yield self.provision(None, self.provider_nsa.urn(), None, '1234')
            self.fail('Should have raised ConnectionNonExistentError')
        except error.ConnectionNonExistentError:
            pass # expected


    @defer.inlineCallbacks
    def testActivation(self):

        d = defer.Deferred()

        def dataPlaneChange(connection_id, active, version_consistent, version, timestamp):
            values = connection_id, active, version_consistent, version, timestamp
            d.callback(values)

        self.sr.registerEventHandler(registry.DATA_PLANE_CHANGE,  dataPlaneChange, registry.NSI2_LOCAL)

        _,_,cid,sp = yield self.reserve(None, self.provider_nsa.urn(), None, None, None, None, self.service_params)
        yield self.reserveCommit(None, self.provider_nsa.urn(), None, cid)
        yield self.provision(None, self.provider_nsa.urn(), None, cid)
        connection_id, active, version_consistent, version, timestamp = yield d
        self.failUnlessEqual(cid, connection_id)
        self.failUnlessEqual(active, True)
        self.failUnlessEqual(version_consistent, True)

        #yield self.release(  None, self.provider_nsa.urn(), None, cid)
        yield self.terminate(None, self.provider_nsa.urn(), None, cid)


    @defer.inlineCallbacks
    def testReserveAbort(self):

        # these need to be constructed such that there is only one label option
        source_stp  = nsa.STP('Aruba', 'A1', labels=[ nsa.Label(nml.ETHERNET_VLAN, '2') ] )
        dest_stp    = nsa.STP('Aruba', 'A3', labels=[ nsa.Label(nml.ETHERNET_VLAN, '2') ] )
        start_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
        end_time   = datetime.datetime.utcnow() + datetime.timedelta(seconds=10)
        service_params = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp, 200)

        _,_,cid,sp = yield self.reserve(None, self.provider_nsa.urn(), None, None, None, None, self.service_params)
        yield self.reserveAbort(None, self.provider_nsa.urn(), None, cid)
        # try to reserve the same resources
        _,_,cid,sp = yield self.reserve(None, self.provider_nsa.urn(), None, None, None, None, self.service_params)

