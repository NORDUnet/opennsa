from twisted.trial import unittest

from zope.interface.verify import verifyObject

from opennsa.interface import INSIProvider, INSIRequester

from opennsa import aggregator
from opennsa.backends.common import genericbackend
from opennsa.protocols.nsi2 import provider


class InterfaceTest(unittest.TestCase):

    def testGenericBackend(self):
        simple_backend = genericbackend.GenericBackend('network', None, None, None, None)
        verifyObject(INSIProvider, simple_backend)


    def testAggregator(self):
        aggr = aggregator.Aggregator('network', None, None, None, None, None, None, None)
        verifyObject(INSIProvider, aggr)
        verifyObject(INSIRequester, aggr)

    testAggregator.skip = 'aggregator not complete yet'

    def testProvider(self):
        prov = provider.Provider(None, None)
        verifyObject(INSIRequester, prov)

    testProvider.skip = 'provider not complete yet'


