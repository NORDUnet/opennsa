from twisted.trial import unittest

from zope.interface.verify import verifyObject

from opennsa.interface import INSIProvider, INSIRequester

from opennsa import registry
from opennsa import aggregator
from opennsa.backends.common import genericbackend




class InterfaceTest(unittest.TestCase):

    def setUp(self):
        self.sr = registry.ServiceRegistry()


    def testGenericBackend(self):
        simple_backend = genericbackend.GenericBackend('network', None, None, None)
        verifyObject(INSIProvider, simple_backend)
#    testGenericBackend.skip = 'Interface undergoing overhaul'


    def testAggregator(self):

        aggr = aggregator.Aggregator('network', None, self.sr, None, None)

        verifyObject(INSIProvider, simple_backend)

    testAggregator.skip = "skip"

