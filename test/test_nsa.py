from twisted.trial import unittest

from opennsa import nsa


class LabelTest(unittest.TestCase):


    def testLabelParsing(self):

        self.assertEquals(nsa.Label('', '1,2').values,          [ (1,2) ] )
        self.assertEquals(nsa.Label('', '1,2,3').values,        [ (1,3) ] )
        self.assertEquals(nsa.Label('', '1-2,3').values,        [ (1,3) ] )
        self.assertEquals(nsa.Label('', '1-3,2').values,        [ (1,3) ] )
        self.assertEquals(nsa.Label('', '1-3,3,1-2').values,    [ (1,3) ] )
        self.assertEquals(nsa.Label('', '2-4,8,1-3').values,    [ (1,4), (8,8) ] )


    def testLabelIntersection(self):

        l12  = nsa.Label('', '1,2')
        l123 = nsa.Label('', '1,2,3')
        l234 = nsa.Label('', '2-4')
        l48  = nsa.Label('', '4-8')

        self.assertEquals( l12.intersect(l12).values,   [ (1,2) ] )
        self.assertEquals( l12.intersect(l123).values,  [ (1,2) ] )
        self.assertEquals( l12.intersect(l234).values,  [ (2,2) ] )
        self.assertEquals( l123.intersect(l234).values, [ (2,3) ] )
        self.assertEquals( l234.intersect(l48).values,  [ (4,4) ] )

        self.assertRaises(nsa.EmptyLabelSet, l12.intersect, l48)


    def testLabelValueEnumeration(self):

        self.assertEquals(nsa.Label('', '1-2,3').enumerateValues(),        [ 1,2,3 ] )
        self.assertEquals(nsa.Label('', '1-3,2').enumerateValues(),        [ 1,2,3 ] )
        self.assertEquals(nsa.Label('', '1-3,3,1-2').enumerateValues(),    [ 1,2,3 ] )
        self.assertEquals(nsa.Label('', '2-4,8,1-3').enumerateValues(),    [ 1,2,3,4,8 ] )


    def testContainedLabelsIntersection(self):

        self.failUnlessEquals(nsa.Label('', '80-89').intersect(nsa.Label('','81-82')).enumerateValues(), [ 81,82] )


    def testIntersectedLabelUnderAndSingleValued(self):

        self.failUnlessRaises(nsa.EmptyLabelSet, nsa.Label('', '1781-1784').intersect, nsa.Label('', '1780-1780') )


    def testNetworkServiceAgent(self):

        agent = nsa.NetworkServiceAgent('id', 'http://localhost:8888')
        host, port = agent.getHostPort()
        self.failUnlessEqual(host, 'localhost')
        self.failUnlessEqual(port, 8888)

