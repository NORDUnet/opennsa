"""
Tests for the opennsa service.
"""

import os
import uuid
import time
import datetime
import StringIO

from twisted.trial import unittest
from twisted.internet import defer, reactor

from opennsa import nsa, setup, event
from opennsa.backends import dud

from . import topology as testtopology


class ServiceTest(unittest.TestCase):

    def setUp(self):

        self.iports = []

        HOST = 'localhost'
        WSDL_DIR = os.path.join(os.getcwd(), '..', 'wsdl')

        # service

        SERVICES = [ ('Aruba', 9080), ('Bonaire', 9081), ('Curacao',9082) ]

        for network, port in SERVICES:

            topo_source = StringIO.StringIO(testtopology.TEST_TOPOLOGY)
            backend = dud.DUDNSIBackend(network)
            es = event.EventHandlerRegistry()
            factory = setup.createService(network, [ topo_source ], backend, es, HOST, port, WSDL_DIR)

            iport = reactor.listenTCP(port, factory, interface='localhost')
            self.iports.append(iport)

        # client

        CLIENT_PORT = 7080

        self.client, client_factory  = setup.createClient(HOST, CLIENT_PORT, WSDL_DIR)
        self.client_nsa = nsa.NetworkServiceAgent('OpenNSA-Test-Client', 'nsa://localhost:%i' % CLIENT_PORT)

        client_iport = reactor.listenTCP(CLIENT_PORT, client_factory)
        self.iports.append(client_iport)


    def tearDown(self):
        for iport in self.iports:
            iport.stopListening()


    @defer.inlineCallbacks
    def testBasicConnectionLifeCycle(self):

        provider = nsa.Network('Aruba', nsa.NetworkServiceAgent('Aruba-OpenNSA', 'http://localhost:9080/NSI/services/ConnectionService'))

        source_stp      = nsa.STP('Aruba', 'A1' )
        dest_stp        = nsa.STP('Aruba', 'A2')
        #dest_stp        = nsa.STP('Bonaire', 'B3')
        #dest_stp        = nsa.STP('Curacao', 'C3')

        start_time = datetime.datetime.utcfromtimestamp(time.time() + 1.5 )
        end_time   = datetime.datetime.utcfromtimestamp(time.time() + 120 )

        bwp = nsa.BandwidthParameters(200)
        service_params  = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp, bandwidth=bwp)
        global_reservation_id = 'urn:uuid:' + str(uuid.uuid1())
        connection_id         = 'conn-id1'

        yield self.client.reserve(self.client_nsa, provider.nsa, None, global_reservation_id, 'Test Connection', connection_id, service_params)

        qr = yield self.client.query(self.client_nsa, provider.nsa, None, "Summary", connection_ids = [ connection_id ] )
        self.assertEquals(qr.reservationSummary[0].connectionState, 'Reserved')

        yield self.client.provision(self.client_nsa, provider.nsa, None, connection_id)

        qr = yield self.client.query(self.client_nsa, provider.nsa, None, "Summary", connection_ids = [ connection_id ] )
        self.assertEquals(qr.reservationSummary[0].connectionState, 'Provisioned')

        yield self.client.release(self.client_nsa, provider.nsa, None, connection_id)

        qr = yield self.client.query(self.client_nsa, provider.nsa, None, "Summary", connection_ids = [ connection_id ] )
        self.assertEquals(qr.reservationSummary[0].connectionState, 'Scheduled')

        yield self.client.terminate(self.client_nsa, provider.nsa, None, connection_id)

        qr = yield self.client.query(self.client_nsa, provider.nsa, None, "Summary", connection_ids = [ connection_id ] )
        self.assertEquals(qr.reservationSummary[0].connectionState, 'Terminated')

        # give the service side time to dump its connections
        # this prevents finishing the test with a dirty reactor
        from twisted.internet import task
        d = task.deferLater(reactor, 0.01, lambda : None)
        yield d

