import time, datetime

from twisted.trial import unittest
from twisted.internet import defer

from dateutil.tz import tzutc

from opennsa import nsa, registry, database
from opennsa.topology import nml
from opennsa.backends import dud



class DUDBackendTest(unittest.TestCase):

    def setUp(self):

        self.sr = registry.ServiceRegistry()
        self.backend = dud.DUDNSIBackend('TestDUD', self.sr)
        self.backend.startService()

        database.setupDatabase('ontest', 'htj', 'htj')

        source_stp  = nsa.STP('Aruba', 'A1', labels=[ nsa.Label(nml.ETHERNET_VLAN, '1-2') ] )
        dest_stp    = nsa.STP('Aruba', 'A3', labels=[ nsa.Label(nml.ETHERNET_VLAN, '2-3') ] )
        start_time = datetime.datetime.fromtimestamp(time.time() + .5) #, tzutc() )
        end_time   = datetime.datetime.fromtimestamp(time.time() + 10,) # tzutc() )
        bandwidth = 200

        self.provider_nsa   = nsa.NetworkServiceAgent('testnsa', 'http://example.org/nsa')
        self.service_params = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp, bandwidth)

        # just so we don't have to put them in the test code
        self.reserve   = self.sr.getHandler(registry.RESERVE,   registry.NSI2_LOCAL)
        self.provision = self.sr.getHandler(registry.PROVISION, registry.NSI2_LOCAL)
        self.release   = self.sr.getHandler(registry.RELEASE,   registry.NSI2_LOCAL)
        self.terminate = self.sr.getHandler(registry.TERMINATE, registry.NSI2_LOCAL)


    def tearDown(self):
        return self.backend.stopService()


    @defer.inlineCallbacks
    def testBasicUsage(self):

        _,_,cid,sp = yield self.reserve(None, self.provider_nsa.urn(), None, None, None, None, self.service_params)
        yield self.terminate(None, self.provider_nsa.urn(), None, cid)


    @defer.inlineCallbacks
    def testProvisionUsage(self):

        _,_,cid,sp = yield self.reserve(None, self.provider_nsa.urn(), None, None, None, None, self.service_params)
        yield self.provision(None, self.provider_nsa.urn(), None, cid)
        yield self.terminate(None, self.provider_nsa.urn(), None, cid)


    @defer.inlineCallbacks
    def testProvisionReleaseUsage(self):

        _,_,cid,sp = yield self.reserve(None, self.provider_nsa.urn(), None, None, None, None, self.service_params)
        yield self.provision(None, self.provider_nsa.urn(), None, cid)
        yield self.release(  None, self.provider_nsa.urn(), None, cid)
        yield self.terminate(None, self.provider_nsa.urn(), None, cid)

