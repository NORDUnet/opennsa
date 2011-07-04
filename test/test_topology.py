from twisted.trial import unittest

from opennsa import nsa, topology


TEST_TOPOLOGY_1 = """
{
    "Denmark"   : {
      "address"   : "addr-dk",
      "endpoints" : [
        { "name" : "DK-Tjele",          "config" : "1234"                                                                   },
        { "name" : "DK-Hirtshals",      "config" : "params",    "dest-network" : "Norway",  "dest-ep" : "NO-Kristianssand"  },
        { "name" : "DK-Frederikshavn",  "config" : "redu",      "dest-network" : "Sweden",  "dest-ep" : "SE-Goteborg"       },
        { "name" : "DK-Orestad",        "config" : "shorty",    "dest-network" : "Sweden",  "dest-ep" : "SE-Malmo"          }
      ]
    },

    "Sweden"    : {
      "address"   : "addr-se",
      "endpoints" : [
        { "name" : "SE-Malmo",          "config" : "kalmar",    "dest-network" : "Denmark", "dest-ep" : "DK-Orestad"        },
        { "name" : "SE-Goteborg",       "config" : "nocod",     "dest-network" : "Denmark", "dest-ep" : "DK-Frederikshavn"  },
        { "name" : "SE-NSC",            "config" : "scrus"                                                                  }
      ]
    },

    "Norway"    : {
      "address"   : "addr-no",
      "endpoints" : [
        { "name" : "NO-Kristianssand",  "config" : "southty",   "dest-network" : "Denmark", "dest-ep" : "DK-Hirtshals"      },
        { "name" : "NO-Trondheim",      "config" : "goodlife"                                                               }
      ]
    }
}
"""


TEST_LINKS_1 = [
    {
      'source_network'  : 'Denmark',
      'source_endpoint' : 'DK-Tjele',
      'dest_network'    : 'Sweden',
      'dest_endpoint'   : 'SE-NSC',
      'links'           :  [ [ nsa.STPPair( nsa.STP('Denmark', 'DK-Frederikshavn'), nsa.STP('Sweden', 'SE-Goteborg') ) ],
                             [ nsa.STPPair( nsa.STP('Denmark', 'DK-Orestad'),       nsa.STP('Sweden', 'SE-Malmo') )    ]
                           ]
    },

    {
      'source_network'  : 'Norway',
      'source_endpoint' : 'NO-Trondheim',
      'dest_network'    : 'Sweden',
      'dest_endpoint'   : 'SE-NSC',
      'links'           : [ [ nsa.STPPair( nsa.STP('Norway', 'NO-Kristianssand'),  nsa.STP('Denmark', 'DK-Hirtshals') ),
                              nsa.STPPair( nsa.STP('Denmark', 'DK-Frederikshavn'), nsa.STP('Sweden', 'SE-Goteborg') )
                            ],
                            [ nsa.STPPair( nsa.STP('Norway', 'NO-Kristianssand'),  nsa.STP('Denmark', 'DK-Hirtshals') ),
                              nsa.STPPair( nsa.STP('Denmark', 'DK-Orestad'),       nsa.STP('Sweden', 'SE-Malmo') )
                            ]
                          ]
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
            source_stp = nsa.STP(ts['source_network'], ts['source_endpoint'])
            dest_stp   = nsa.STP(ts['dest_network'], ts['dest_endpoint'])
            links = t.findLinks(source_stp, dest_stp)
            for link in links:
                self.assertEquals(ts['source_network'],  link.source_stp.network)
                self.assertEquals(ts['source_endpoint'], link.source_stp.endpoint)
                self.assertEquals(ts['dest_network'],    link.dest_stp.network)
                self.assertEquals(ts['dest_endpoint'],   link.dest_stp.endpoint)

            leps = [ link.endpoint_pairs for link in links ]

            for l in ts['links']:
                self.assertIn(l, leps)

