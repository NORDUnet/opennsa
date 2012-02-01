"""
Tests for opennsa.jsonrpc module.
"""

import json
import uuid
import urlparse
import StringIO

from twisted.trial import unittest
from twisted.internet import defer, reactor

from opennsa import nsa, setup, jsonrpc
from opennsa.backends import dud

from . import topology


class GenericSingleNSATestCase: #(unittest.TestCase):

    @defer.inlineCallbacks
    def testConnectionLifeCycle(self):

        provider_net    = nsa.Network('A', nsa.NetworkServiceAgent('nsa://localhost:4321') )

        source_stp      = nsa.STP('A', 'A1' )
        dest_stp        = nsa.STP('A', 'A2' )
        service_params  = nsa.ServiceParameters('', '', source_stp, dest_stp)

        reservation_id = uuid.uuid1().hex
        conn_id = 'cli-ccid-test'

        rd = self.client_service.addReservation(provider_net.nsa, conn_id)

        yield self.client.reserve(self.client_nsa, provider_net.nsa, None, reservation_id, 'Test Connection', conn_id, service_params)
        yield rd # await confirmation

        # _ = yield client.query(client_nsa, provider_net.nsa, None, None)

        _ = yield self.client.provision(self.client_nsa, provider_net.nsa, None, conn_id)

        # _ = yield client.query(client_nsa, provider_net.nsa, None, None)

        _ = yield self.client.releaseProvision(self.client_nsa, provider_net.nsa, None, conn_id)

        # _ = yield client.query(client_nsa, provider_net.nsa, None, None)

        _ = yield self.client.terminateReservation(self.client_nsa, provider_net.nsa, None, conn_id)



class JSONRPCSingleNSATestCase(GenericSingleNSATestCase, unittest.TestCase):

    CLIENT_PORT = 4810

    def setUp(self):

        # service
        network_name = 'A'
        top = json.loads(topology.SIMPLE_TOPOLOGY)

        network_info = top[network_name]

        nsa_url = urlparse.urlparse(network_info['address']).netloc
        port = int(nsa_url.split(':',2)[1])

        backend = dud.DUDNSIBackend(network_name)
        service_factory = setup.createService(network_name, StringIO.StringIO(topology.SIMPLE_TOPOLOGY), backend)

        self.service_iport = reactor.listenTCP(port, service_factory)

        # client
        self.client, self.client_service, client_factory  = setup.createClient()
        self.client_nsa = nsa.NetworkServiceAgent('nsa://localhost:%i' % self.CLIENT_PORT)

        self.client_iport = reactor.listenTCP(self.CLIENT_PORT, client_factory)


    def tearDown(self):

        self.client_iport.stopListening()
        self.service_iport.stopListening()

