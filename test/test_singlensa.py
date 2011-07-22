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

        client_nsa      = nsa.NetworkServiceAgent('nsa://none:0')
        provider_net    = nsa.Network('A', nsa.NetworkServiceAgent('nsa://localhost:4321') )

        source_stp      = nsa.STP('A', 'A1' )
        dest_stp        = nsa.STP('A', 'A2' )
        service_params  = nsa.ServiceParameters('', '', source_stp, dest_stp)

        reservation_id = uuid.uuid1().hex
        conn_id = 'cli-ccid-test'

        yield self.proxy.reserve(client_nsa, provider_net.nsa, conn_id, reservation_id, 'Test Connection', service_params, None)

        # _ = yield proxy.query(client_nsa, provider_net.nsa, None, None)

        _ = yield self.proxy.provision(client_nsa, provider_net.nsa, conn_id, None)

        # _ = yield proxy.query(client_nsa, provider_net.nsa, None, None)

        _ = yield self.proxy.releaseProvision(client_nsa, provider_net.nsa, conn_id, None)

        # _ = yield proxy.query(client_nsa, provider_net.nsa, None, None)

        _ = yield self.proxy.cancelReservation(client_nsa, provider_net.nsa, conn_id, None)



class JSONRPCSingleNSATestCase(GenericSingleNSATestCase, unittest.TestCase):


    def setUp(self):

        # service
        network_name = 'A'
        top = json.loads(topology.SIMPLE_TOPOLOGY)

        network_info = top[network_name]

        nsa_url = urlparse.urlparse(network_info['address']).netloc
        port = int(nsa_url.split(':',2)[1])

        proxy = dud.DUDNSIBackend(network_name)
        factory = setup.createFactory(network_name, StringIO.StringIO(topology.SIMPLE_TOPOLOGY), proxy)

        self.iport = reactor.listenTCP(port, factory)

        # client
        self.proxy = jsonrpc.JSONRPCNSIClient()


    def tearDown(self):

        self.iport.stopListening()

