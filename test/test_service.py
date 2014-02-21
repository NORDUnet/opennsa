"""
Tests for the opennsa service.
"""

import os
import uuid
import json
import time
import datetime
import StringIO

from twisted.trial import unittest
from twisted.internet import defer, reactor
from twisted.application import service as twistedservice 

from opennsa import config, setup, nsa, error
from opennsa.protocols import nsi2

from . import topology


class ServiceTest(unittest.TestCase):

    def setUp(self):

        self.iports = []

        HOST = 'localhost'

        test_config_file = os.path.expanduser('~/.opennsa-test.json')
        test_config = json.load( open(test_config_file) )
        # service
        self.service = twistedservice.MultiService()

        SERVICE_SPECS = [ ('Aruba',     9080, topology.ARUBA_TOPOLOGY),
                          ('Bonaire',   9081, topology.BONAIRE_TOPOLOGY),
                          ('Curacao',   9082, topology.CURACAO_TOPOLOGY),
                          ('Dominica',  9083, topology.DOMINICA_TOPOLOGY)   ]

        for network, port, topo in SERVICE_SPECS:

            service_config = {
                config.HOST                 : 'localhost',
                config.PORT                 : port,
                config.NETWORK_NAME         : network,
                config.TLS                  : False,
                config.NRM_MAP_FILE         : StringIO.StringIO(topo),
                config.DATABASE             : test_config['database'],
                config.DATABASE_USER        : test_config['database-user'],
                config.DATABASE_PASSWORD    : test_config['database-password'],
                'backend'                   : {'': {'_backend_type': 'dud'}}
            }

            setup.OpenNSAService(service_config).setServiceParent(self.service)

        # client

        self.service.startService()

        CLIENT_PORT = 7080

        self.client, client_factory  = nsi2.createRequesterClient(HOST, CLIENT_PORT)
        self.client_nsa = nsa.NetworkServiceAgent('OpenNSA-Test-Client', 'http://localhost:%i/NSI/CS2' % CLIENT_PORT)

        self.client_iport = reactor.listenTCP(CLIENT_PORT, client_factory)


    def tearDown(self):
        self.client_iport.stopListening()
        return self.service.stopService()


    @defer.inlineCallbacks
    def testBasicConnectionLifeCycle(self):

        provider_nsa = nsa.NetworkServiceAgent('urn:aruba:nsa', 'http://localhost:9080/NSI/CS2')

        source_stp      = nsa.STP('Aruba', 'A1' )
        dest_stp        = nsa.STP('Aruba', 'A2')

        start_time = datetime.datetime.utcfromtimestamp(time.time() + 1.5 )
        end_time   = datetime.datetime.utcfromtimestamp(time.time() + 120 )

        bandwidth = 200
        service_params  = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp, bandwidth)
        global_reservation_id = 'urn:uuid:' + str(uuid.uuid1())
        connection_id         = 'conn-id1'

        yield self.client.reserve(self.client_nsa, provider_nsa, None, global_reservation_id, 'Test Connection', connection_id, service_params)

        qr = yield self.client.query(self.client_nsa, provider_nsa, None, "Summary", connection_ids = [ connection_id ] )
        self.assertEquals(qr.reservationSummary[0].connectionState, 'Reserved')

        yield self.client.provision(self.client_nsa, provider_nsa, None, connection_id)

        qr = yield self.client.query(self.client_nsa, provider_nsa, None, "Summary", connection_ids = [ connection_id ] )
        self.assertEquals(qr.reservationSummary[0].connectionState, 'Provisioned')

        yield self.client.release(self.client_nsa, provider_nsa, None, connection_id)

        qr = yield self.client.query(self.client_nsa, provider_nsa, None, "Summary", connection_ids = [ connection_id ] )
        self.assertEquals(qr.reservationSummary[0].connectionState, 'Scheduled')

        yield self.client.terminate(self.client_nsa, provider_nsa, None, connection_id)

        qr = yield self.client.query(self.client_nsa, provider_nsa, None, "Summary", connection_ids = [ connection_id ] )
        self.assertEquals(qr.reservationSummary[0].connectionState, 'Terminated')

        # give the service side time to dump its connections
        # this prevents finishing the test with a dirty reactor
        from twisted.internet import task
        d = task.deferLater(reactor, 0.01, lambda : None)
        yield d

    testBasicConnectionLifeCycle.skip = 'Service no longer exist in its old form'


    @defer.inlineCallbacks
    def testNoRouteReservation(self):

        provider = nsa.Network('Aruba', nsa.NetworkServiceAgent('Aruba-OpenNSA', 'http://localhost:9080/NSI/services/ConnectionService'))

        source_stp      = nsa.STP('Hawaii', 'H1' )
        dest_stp        = nsa.STP('Aruba', 'A2')

        start_time = datetime.datetime.utcfromtimestamp(time.time() + 1.5 )
        end_time   = datetime.datetime.utcfromtimestamp(time.time() + 120 )

        bandwidth = 200
        service_params  = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp, bandwidth)
        connection_id         = 'conn-id1'

        try:
            yield self.client.reserve(self.client_nsa, provider.nsa, None, None, '', connection_id, service_params)
            self.fail('Reserve call should have failed')
        except error.ReserveError as e:
            self.failUnlessIn('Could not find a path', str(e))
        errors = self.flushLoggedErrors(error.TopologyError)
        self.assertEqual(len(errors), 1)

    testNoRouteReservation.skip = 'Service no longer exist in its old form'

