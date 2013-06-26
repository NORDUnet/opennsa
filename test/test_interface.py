from twisted.trial import unittest

from zope.interface.verify import verifyObject

from opennsa.interface import INSIProvider, INSIRequester

from opennsa import aggregator
from opennsa.backends.common import genericbackend




class InterfaceTest(unittest.TestCase):

    def testGenericBackend(self):
        simple_backend = genericbackend.GenericBackend('network', None, None, None)
        verifyObject(INSIProvider, simple_backend)


    def testAggregator(self):
        aggr = aggregator.Aggregator('network', None, None, None, None)
        verifyObject(INSIProvider, aggr)
    testAggregator.skip = "skip, aggregator not complete yet"

