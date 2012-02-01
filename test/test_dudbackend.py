import time, datetime

from twisted.trial import unittest
from twisted.internet import defer

from opennsa import error, nsa
from opennsa.backends import dud




class DUDBackendTest(unittest.TestCase):

    def setUp(self):
        self.backend = dud.DUDNSIBackend('TestDUD')

        source_stp  = nsa.STP('Aruba', 'A1' )
        dest_stp    = nsa.STP('Aruba', 'A3' )
        start_time = datetime.datetime.utcfromtimestamp(time.time() + 0.1 )
        end_time   = datetime.datetime.utcfromtimestamp(time.time() + 10 )
        bwp = nsa.BandwidthParameters(200)

        self.service_params  = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp, bandwidth=bwp)


    @defer.inlineCallbacks
    def testBasicUsage(self):

        conn = self.backend.createConnection('A1', 'A3', self.service_params)

        yield conn.reserve()

        da, dp = conn.provision()
        yield da # provision acknowledged
        yield dp # provision performed

        yield conn.release()

        yield conn.terminate()

