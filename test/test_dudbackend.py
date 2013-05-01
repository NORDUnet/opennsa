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

        database.setupDatabase('ontest', 'htj', 'htj')

        source_stp  = nsa.STP('Aruba', 'A1', labels=[ nsa.Label(nml.ETHERNET_VLAN, '1') ] )
        dest_stp    = nsa.STP('Aruba', 'A3', labels=[ nsa.Label(nml.ETHERNET_VLAN, '1') ] )
        start_time = datetime.datetime.fromtimestamp(time.time() + 0.1, tzutc() )
        end_time   = datetime.datetime.fromtimestamp(time.time() + 10,  tzutc() )
        bandwidth = 200

        self.provider_nsa   = nsa.NetworkServiceAgent('testnsa', 'http://example.org/nsa')
        self.service_params = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp, bandwidth)



    @defer.inlineCallbacks
    def testBasicUsage(self):

        reserve   = self.sr.getHandler(registry.RESERVE,   registry.NSI2_LOCAL)
        provision = self.sr.getHandler(registry.PROVISION, registry.NSI2_LOCAL)
        release   = self.sr.getHandler(registry.RELEASE,   registry.NSI2_LOCAL)
        terminate = self.sr.getHandler(registry.TERMINATE, registry.NSI2_LOCAL)

        _,_,cid,sp = yield reserve(None, self.provider_nsa.urn(), None, None, None, None, self.service_params)

        yield provision(None, self.provider_nsa.urn(), None, cid)
        yield release(  None, self.provider_nsa.urn(), None, cid)
        yield terminate(None, self.provider_nsa.urn(), None, cid)

