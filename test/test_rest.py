import os, json
from StringIO import StringIO

from twisted.trial import unittest
from twisted.internet import reactor, defer, task
from twisted.web import resource, server
from twisted.application import internet

from opennsa import nsa, provreg, database, aggregator, config, plugin
from opennsa.topology import nml, nrm, linkvector
from opennsa.backends import dud
from opennsa.protocols import rest, nsi2

from . import topology, common

# http client
from twisted.web.client import Agent, FileBodyProducer, readBody
from twisted.web.http_headers import Headers





class RestInterfaceTest(unittest.TestCase):

    PORT = 8180

    network = 'aruba:topology'
    provider_agent  = nsa.NetworkServiceAgent('aruba:nsa', 'dud_endpoint2')


    def setUp(self):
        tcf = os.path.expanduser('~/.opennsa-test.json')
        tc = json.load( open(tcf) )
        database.setupDatabase( tc['database'], tc['database-user'], tc['database-password'])

        self.requester = common.DUDRequester()

        self.clock = task.Clock()

        nrm_ports = nrm.parsePortSpec(StringIO(topology.ARUBA_TOPOLOGY))
        network_topology = nml.createNMLNetwork(nrm_ports, self.network, self.network)

        self.backend = dud.DUDNSIBackend(self.network, nrm_ports, None, {}) # we set the parent later
        self.backend.scheduler.clock = self.clock

        link_vector = linkvector.LinkVector( [ self.network ] )

        pl = plugin.BasePlugin()
        pl.init( { config.NETWORK_NAME: self.network }, None )

        pr = provreg.ProviderRegistry( { self.provider_agent.urn() : self.backend }, {} )
        self.aggregator = aggregator.Aggregator(self.network, self.provider_agent, network_topology, link_vector, None, pr, [], pl) # we set the parent later

        self.backend.parent_requester = self.aggregator

        # provider protocol
        http_top_resource = resource.Resource()

        rest.setupService(self.aggregator, http_top_resource)

        # we need this for the aggregator not to blow up
        cs2_prov = nsi2.setupProvider(self.aggregator, http_top_resource)
        self.aggregator.parent_requester = cs2_prov

        provider_factory = server.Site(http_top_resource)
        self.provider_service = internet.TCPServer(self.PORT, provider_factory)

        # start engines!
        self.backend.startService()
        self.provider_service.startService()


    @defer.inlineCallbacks
    def tearDown(self):

        self.backend.stopService()
        self.provider_service.stopService()

        from opennsa.backends.common import genericbackend
        # keep it simple...
        yield genericbackend.GenericBackendConnections.deleteAll()
        yield database.SubConnection.deleteAll()
        yield database.ServiceConnection.deleteAll()

        # close database connections, so we don't run out
        from twistar.registry import Registry
        Registry.DBPOOL.close()



    @defer.inlineCallbacks
    def testInvalidNetwork(self):

        agent = Agent(reactor)

        header = Headers({'User-Agent': ['OpenNSA Test Client'], 'Host': ['localhost'] } )

        payload = '''{ "source" : "nordu.net:s1", "destination" : "surfnet.nl:ps", "end" : "2016-01-13T08:08:08Z" }'''

        create_url = 'http://localhost:%i%s' % (self.PORT, rest.PATH)
        producer = FileBodyProducer(StringIO(payload))

        d = agent.request('POST', create_url, header, producer)

        resp = yield d

        self.failUnlessEqual(resp.code, 400, 'Service did not return request error')


    @defer.inlineCallbacks
    def testCreateCommitProvision(self):

        agent = Agent(reactor)

        header = Headers({'User-Agent': ['OpenNSA Test Client'], 'Host': ['localhost'] } )

        payload = '''{ "source" : "aruba:topology:ps?vlan=1783", "destination" : "aruba:topology:bon?vlan=1783" }'''

        create_url = 'http://localhost:%i%s' % (self.PORT, rest.PATH)
        producer = FileBodyProducer(StringIO(payload))

        resp = yield agent.request('POST', create_url, header, producer)

        self.failUnlessEqual(resp.code, 201, 'Service did not return created')
        if not resp.headers.hasHeader('location'):
            self.fail('No location header in create response')

        conn_url = 'http://localhost:%i%s' % (self.PORT, resp.headers.getRawHeaders('location')[0])

        # so... the connection will not necesarely have moved into reserveheld or all sub-connections might not even be in place yet
        # we cannot really commit until we are in created and ReserveHeld
        # the clock doesn't really do anything here (not scheduling related)

        yield task.deferLater(reactor, 0.1, self._createCommitProvisionCB, agent, conn_url, header)


    @defer.inlineCallbacks
    def _createCommitProvisionCB(self, agent, conn_url, header):

        c_resp = yield agent.request('GET', conn_url, header)
        body = yield readBody(c_resp)
        c_info = json.loads(body)
        self.failUnlessEquals(c_info['reservation_state'], 'ReserveHeld', 'State did not transit to held after creation')

        status_url = conn_url + '/status'

        # commit
        producer2 = FileBodyProducer(StringIO('commit'))
        resp2 = yield agent.request('POST', status_url, header, producer2)

        self.failUnlessEqual(resp2.code, 200, 'Service did not return OK after commit')

        # should do new call here..

        c_resp = yield agent.request('GET', conn_url, header)
        body = yield readBody(c_resp)
        c_info2 = json.loads(body)

        self.failUnlessEquals(c_info2['reservation_state'], 'ReserveStart', 'State did not transit after commit')

        # provision
        producer3 = FileBodyProducer(StringIO('provision'))
        resp3 = yield agent.request('POST', status_url, header, producer3)
        self.failUnlessEqual(resp3.code, 200, 'Service did not return OK after provision')

        # give the provider a bit of time to switch
        yield task.deferLater(reactor, 0.1, self._createCommitProvisionCB2, agent, conn_url, header)


    @defer.inlineCallbacks
    def _createCommitProvisionCB2(self, agent, conn_url, header):

        resp = yield agent.request('GET', conn_url, header)
        data = yield readBody(resp)
        conn_info = json.loads(data)
        self.failUnlessEquals(conn_info['provision_state'], 'Provisioned', 'State did not transit to provisioned after provision')

