from twisted.trial import unittest

from opennsa import topology


TEST_TOPOLOGY_1 = """
{
    "Denmark"   : [
        { "name" : "DK-Tjele",          "config" : "1234"                                                                   },
        { "name" : "DK-Hirtshals",      "config" : "params",    "dest-network" : "Norway",  "dest-ep" : "NO-Kristianssand"  },
        { "name" : "DK-Frederikshavn",  "config" : "redu",      "dest-network" : "Sweden",  "dest-ep" : "SE-Goteborg"       },
        { "name" : "DK-Orestad",        "config" : "shorty",    "dest-network" : "Sweden",  "dest-ep" : "SE-Malmo"          }
    ],

    "Sweden"    : [
        { "name" : "SE-Malmo",          "config" : "kalmar",    "dest-network" : "Denmark", "dest-ep" : "DK-Orestad"        },
        { "name" : "SE-Goteborg",       "config" : "nocod",     "dest-network" : "Denmark", "dest-ep" : "DK-Frederikshavn"  },
        { "name" : "SE-NSC",            "config" : "scrus"                                                                  }
    ],

    "Norway"    : [
        { "name" : "NO-Kristianssand",  "config" : "southty",   "dest-network" : "Denmark", "dest-ep" : "DK-Hirtshals"      },
        { "name" : "NO-Trondheim",      "config" : "goodlife"                                                               }
    ]
}
"""


TEST_LINKS_1 = [
    {
      'source_network'  : 'Denmark',
      'source_endpoint' : 'DK-Tjele',
      'dest_network'    : 'Sweden',
      'dest_endpoint'   : 'SE-NSC',
      'links'           :  [ [ ('Denmark', 'DK-Frederikshavn', 'Sweden', 'SE-Goteborg') ],
                             [ ('Denmark', 'DK-Orestad', 'Sweden', 'SE-Malmo') ] ]
    },

    {
      'source_network'  : 'Norway',
      'source_endpoint' : 'NO-Trondheim',
      'dest_network'    : 'Sweden',
      'dest_endpoint'   : 'SE-NSC',
      'links'           : [ [ ('Norway', 'NO-Kristianssand', 'Denmark', 'DK-Hirtshals'), ('Denmark', 'DK-Frederikshavn', 'Sweden', 'SE-Goteborg') ],
                            [ ('Norway', 'NO-Kristianssand', 'Denmark', 'DK-Hirtshals'), ('Denmark', 'DK-Orestad', 'Sweden', 'SE-Malmo') ] ]
    }
]



class TopologyTest(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass


    def testParseAndFindLink(self):

        t = topology.Topology()
        t.parseTopology(TEST_TOPOLOGY_1)

        for ts in TEST_LINKS_1:
            links = t.findLinks(ts['source_network'], ts['source_endpoint'], ts['dest_network'], ts['dest_endpoint'])
            for link in links:
                self.assertEquals(ts['source_network'],  link.source_network)
                self.assertEquals(ts['source_endpoint'], link.source_endpoint)
                self.assertEquals(ts['dest_network'],    link.dest_network)
                self.assertEquals(ts['dest_endpoint'],   link.dest_endpoint)

            leps = [ link.endpoint_pairs for link in links ]

            for l in ts['links']:
                self.assertIn(l, leps)

