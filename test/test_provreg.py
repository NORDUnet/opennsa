from twisted.trial import unittest

from opennsa import constants as cnt, error, nsa, provreg



class TestProviderRegistry(unittest.TestCase):

    def setUp(self):
        self.pr = provreg.ProviderRegistry( { cnt.CS2_SERVICE_TYPE : lambda x : x } )


    def testGetProvider(self):

        agent = nsa.NetworkServiceAgent('test', 'http://example.org/nsi', cnt.CS2_SERVICE_TYPE)

        self.pr.spawnProvider(agent, 'testnetwork')
        self.pr.spawnProvider(agent, 'testnetwork2')

        provider1 = self.pr.getProvider('testnetwork') # cnt.URN_OGF_PREFIX + 'test')
        self.failUnlessEqual(provider1.urn(), cnt.URN_OGF_PREFIX + 'test')

        provider2 = self.pr.getProvider('testnetwork2')
        self.failUnlessEqual(provider2.urn(), cnt.URN_OGF_PREFIX + 'test')


    def testUpdatedNetwork(self):

        agent = nsa.NetworkServiceAgent('test', 'http://example.org/nsi', cnt.CS2_SERVICE_TYPE)

        self.pr.spawnProvider(agent, 'testnetwork')
        self.pr.spawnProvider(agent, 'testnetwork2')

        provider2 = self.pr.getProvider('testnetwork2')
        self.failUnlessEqual(provider2.urn(), cnt.URN_OGF_PREFIX + 'test')


    def testMultipleNetworks(self):

        agent = nsa.NetworkServiceAgent('test', 'http://example.org/nsi', cnt.CS2_SERVICE_TYPE)

        fake_provider = 'provider123'
        self.pr.addProvider(agent.urn(), 'testnetwork',  fake_provider)
        self.pr.addProvider(agent.urn(), 'testnetwork2', fake_provider)

        provider1 = self.pr.getProvider('testnetwork')
        self.failUnlessEqual(provider1, fake_provider)

        provider2 = self.pr.getProvider('testnetwork2')
        self.failUnlessEqual(provider2, fake_provider)


    def testMultipleProviders(self):

        agent_a = nsa.NetworkServiceAgent('a', 'http://example.org/nsi-a', cnt.CS2_SERVICE_TYPE)
        agent_b = nsa.NetworkServiceAgent('b', 'http://example.org/nsi-b', cnt.CS2_SERVICE_TYPE)

        fake_provider_a1 = 'provider-a1'
        fake_provider_a2 = 'provider-a2'
        fake_provider_b  = 'provider-b'

        self.pr.addProvider(agent_a.urn(), 'testnetwork_a1', fake_provider_a1)
        self.pr.addProvider(agent_a.urn(), 'testnetwork_a2', fake_provider_a2)
        self.pr.addProvider(agent_b.urn(), 'testnetwork_b',  fake_provider_b)

        provider = self.pr.getProvider('testnetwork_a1')
        self.failUnlessEqual(provider, fake_provider_a1)

        provider = self.pr.getProvider('testnetwork_a2')
        self.failUnlessEqual(provider, fake_provider_a2)

