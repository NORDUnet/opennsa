import os, datetime, json

from twisted.trial import unittest
from twisted.internet import defer, task

from opennsa import config, nsa, registry, database, error, state
from opennsa.topology import nml
from opennsa.backends import ncsvpn



class DUDBackendTest(unittest.TestCase):

    def setUp(self):

        self.clock = task.Clock()

        self.sr = registry.ServiceRegistry()
        self.registry_system = 'ncsvpn-test'

        tcf = os.path.expanduser('~/.opennsa-test.json')
        tc = json.load( open(tcf) )

        ncs_config = {
            config.NCS_SERVICES_URL : tc['ncs-url'],
            config.NCS_USER         : tc['ncs-user'],
            config.NCS_PASSWORD     : tc['ncs-password']
        }

        self.backend = ncsvpn.NCSVPNBackend('Test', self.sr, self.registry_system, ncs_config)
        self.backend.scheduler.clock = self.clock

        self.backend.startService()

        database.setupDatabase( tc['database'], tc['database-user'], tc['database-password'])

        self.requester_nsa = nsa.NetworkServiceAgent('test-requester', 'http://example.org/nsa-test-requester')
        self.provider_nsa  = nsa.NetworkServiceAgent('test-provider',  'http://example.org/nsa-test-provider')

        source_stp  = nsa.STP('ncs', 'hel:ge-1/0/1', labels=[ nsa.Label(nml.ETHERNET_VLAN, '100-102') ] )
        dest_stp    = nsa.STP('ncs', 'sto:ge-1/0/1', labels=[ nsa.Label(nml.ETHERNET_VLAN, '101-104') ] )
        start_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=2)
        end_time   = datetime.datetime.utcnow() + datetime.timedelta(seconds=30)
        bandwidth = 200
        self.service_params = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp, bandwidth)

        # just so we don't have to put them in the test code
        self.reserve        = self.sr.getHandler(registry.RESERVE,        registry.NSI2_LOCAL)
        self.reserveCommit  = self.sr.getHandler(registry.RESERVE_COMMIT, registry.NSI2_LOCAL)
        self.reserveAbort   = self.sr.getHandler(registry.RESERVE_ABORT,  registry.NSI2_LOCAL)
        self.provision      = self.sr.getHandler(registry.PROVISION,      registry.NSI2_LOCAL)
        self.release        = self.sr.getHandler(registry.RELEASE,        registry.NSI2_LOCAL)
        self.terminate      = self.sr.getHandler(registry.TERMINATE,      registry.NSI2_LOCAL)


    @defer.inlineCallbacks
    def tearDown(self):
        from opennsa.backends.common import simplebackend
        # delete all created connections from test database
        yield simplebackend.Simplebackendconnection.deleteAll()
        yield self.backend.stopService()


    @defer.inlineCallbacks
    def testActivation(self):

        d_up = defer.Deferred()
        d_down = defer.Deferred()

        def errorEvent(requester_nsa, provider_nsa, session_security_attr, connection_id, event, connection_states, timestamp, info, ex):
            print "errorEvent", event, info, ex

        def dataPlaneChange(requester_nsa, provider_nsa, session_security_attr, connection_id, dps, timestamp):
            active, version, version_consistent = dps
            values = connection_id, active, version_consistent, version, timestamp
            if active:
                d_up.callback(values)
            else:
                d_down.callback(values)

        self.sr.registerEventHandler(registry.ERROR_EVENT,        errorEvent,      self.registry_system)
        self.sr.registerEventHandler(registry.DATA_PLANE_CHANGE,  dataPlaneChange, self.registry_system)

        _,_,cid,sp = yield self.reserve(self.requester_nsa, self.provider_nsa, None, None, None, None, self.service_params)
        yield self.reserveCommit(self.requester_nsa, self.provider_nsa, None, cid)
        yield self.provision(self.requester_nsa, self.provider_nsa, None, cid)
        self.clock.advance(3)

        connection_id, active, version_consistent, version, timestamp = yield d_up
        self.failUnlessEqual(cid, connection_id)
        self.failUnlessEqual(active, True)
        self.failUnlessEqual(version_consistent, True)

        #yield self.release(self.requester_nsa, self.provider_nsa, None, cid)
        yield self.terminate(self.requester_nsa, self.provider_nsa, None, cid)

        connection_id, active, version_consistent, version, timestamp = yield d_down
        self.failUnlessEqual(cid, connection_id)
        self.failUnlessEqual(active, False)
        self.failUnlessEqual(version_consistent, True)

    testActivation.skip = 'NCS VPN Test Requires NCS lab setup'

