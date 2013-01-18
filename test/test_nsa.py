from twisted.trial import unittest

from opennsa import nsa


class LabelParsingTest(unittest.TestCase):


    def testParseLabel(self):

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

        self.assertEquals( l12.intersect(l123).values,  [ (1,2) ] )
        self.assertEquals( l12.intersect(l234).values,  [ (2,2) ] )
        self.assertEquals( l123.intersect(l234).values, [ (2,3) ] )
        self.assertEquals( l234.intersect(l48).values,  [ (4,4) ] )

        self.assertRaises(nsa.EmptyLabelSet, l12.intersect, l48)

