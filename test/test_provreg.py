from twisted.trial import unittest

from opennsa import constants as cnt, error, nsa, provreg



class TestProviderRegistry(unittest.TestCase):

    def setUp(self):
        self.pr = provreg.ProviderRegistry({}, { cnt.CS2_SERVICE_TYPE : lambda x : x } )


    def testGetProvider(self):

        agent = nsa.NetworkServiceAgent('test', 'http://example.org/nsi', cnt.CS2_SERVICE_TYPE)

        self.pr.spawnProvider(agent, [ 'testnetwork'] )

        provider1 = self.pr.getProvider(cnt.URN_OGF_PREFIX + 'test')
        self.failUnlessEqual(provider1.urn(), cnt.URN_OGF_PREFIX + 'test')

        provider2 = self.pr.getProviderByNetwork('testnetwork')
        self.failUnlessEqual(provider2, cnt.URN_OGF_PREFIX + 'test')


    def testUpdatedNetwork(self):

        agent = nsa.NetworkServiceAgent('test', 'http://example.org/nsi', cnt.CS2_SERVICE_TYPE)

        self.pr.spawnProvider(agent, [ 'testnetwork'] )
        self.pr.spawnProvider(agent, [ 'testnetwork', 'testnetwork2' ] )

        provider2 = self.pr.getProviderByNetwork('testnetwork2')
        self.failUnlessEqual(provider2, cnt.URN_OGF_PREFIX + 'test')


    def testRemovedNetwork(self):
        agent = nsa.NetworkServiceAgent('test', 'http://example.org/nsi', cnt.CS2_SERVICE_TYPE)

        self.pr.spawnProvider(agent, [ 'testnetwork', 'testnetwork2' ] )
        self.pr.spawnProvider(agent, [ 'testnetwork'] )

        self.failUnlessRaises(error.STPResolutionError, self.pr.getProviderByNetwork, 'testnetwork2')


