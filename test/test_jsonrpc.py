from twisted.trial import unittest
from twisted.test import proto_helpers
from twisted.internet import defer

from opennsa import jsonrpc



class JSONRPCTest(unittest.TestCase):

    def setUp(self):

        self.service_transport = proto_helpers.StringTransport()
        self.service_proto = jsonrpc.JSONRPCService()
        self.service_proto.makeConnection(self.service_transport)

        self.client_transport = proto_helpers.StringTransport()
        self.client_proto = jsonrpc.ServiceProxy()
        self.client_proto.makeConnection(self.client_transport)


    def tearDown(self):
        pass


    def pump(self):
        self.service_proto.dataReceived(self.client_transport.value())
        self.client_proto.dataReceived(self.service_transport.value())
        self.service_transport.clear()
        self.client_transport.clear()


    @defer.inlineCallbacks
    def testSumCall(self):

        add = lambda *args : sum(args)
        self.service_proto.registerFunction('add',add)

        d1 = self.client_proto.call('add', 1,2,3)
        self.pump()
        result = yield d1
        self.failUnlessEqual(result, 6)

        d2 = self.client_proto.call('add', 1,2,'sager')
        self.pump()
        try:
            _ = yield d2
            self.fail('Incorrect method arguments should have raised exception')
        except jsonrpc.JSONRPCError,e :
            pass # expected
        except Exception:
            self.fail('Incorrect method arguments raised incorrect exception')


    @defer.inlineCallbacks
    def testNonexistingMethod(self):

        d = self.client_proto.call('stuff', 'arg')
        self.pump()

        try:
            _ = yield d
            self.fail('Calling non-existing method should have raised exception')
        except jsonrpc.NoSuchMethodError:
            pass # expected
        except Exception:
            self.fail('Calling non-existing method raised wrong exception')


