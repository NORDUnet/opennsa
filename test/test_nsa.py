from twisted.trial import unittest

from opennsa import nsa


class LabelParsingTest(unittest.TestCase):


    def testParseAndFindPath(self):

        self.assertEquals(nsa.Label('', '1,2').values,          [ (1,2) ] )
        self.assertEquals(nsa.Label('', '1,2,3').values,        [ (1,3) ] )
        self.assertEquals(nsa.Label('', '1-2,3').values,        [ (1,3) ] )
        self.assertEquals(nsa.Label('', '1-3,2').values,        [ (1,3) ] )
        self.assertEquals(nsa.Label('', '1-3,3,1-2').values,    [ (1,3) ] )
        self.assertEquals(nsa.Label('', '2-4,8,1-3').values,    [ (1,4), (8,8) ] )

