from twisted.trial import unittest

from opennsa import nsa, topology


TEST_TOPOLOGY_1 = """
{
    "Denmark"   : {
      "address"   : "addr-dk",
      "endpoints" : [
        { "name" : "DK-Tjele",     "config" : "1234",   "max-capacity": 1000, "available-capacity": 1000                                                        },
        { "name" : "DK-Hirtshals", "config" : "params", "max-capacity": 1000, "available-capacity": 1000, "dest-network" : "Norway",  "dest-ep" : "NO-Fevik"    },
        { "name" : "DK-Saeby",     "config" : "redu",   "max-capacity":  500, "available-capacity":  500, "dest-network" : "Sweden",  "dest-ep" : "SE-Goteborg" },
        { "name" : "DK-Orestad",   "config" : "shorty", "max-capacity": 1000, "available-capacity": 1000, "dest-network" : "Sweden",  "dest-ep" : "SE-Malmo"    }
      ]
    },

    "Sweden"    : {
      "address"   : "addr-se",
      "endpoints" : [
        { "name" : "SE-Malmo",     "config" : "kalmar", "max-capacity": 1000, "available-capacity": 1000, "dest-network" : "Denmark", "dest-ep" : "DK-Orestad"  },
        { "name" : "SE-Goteborg",  "config" : "nocod",  "max-capacity":  500, "available-capacity":  500, "dest-network" : "Denmark", "dest-ep" : "DK-Saeby"    },
        { "name" : "SE-NSC",       "config" : "scrus",  "max-capacity": 1000, "available-capacity": 1000                                                        }
      ]
    },

    "Norway"    : {
      "address"   : "addr-no",
      "endpoints" : [
        { "name" : "NO-Fevik",     "config" : "southty", "max-capacity": 1000, "available-capacity": 1000, "dest-network" : "Denmark", "dest-ep" : "DK-Hirtshals"   },
        { "name" : "NO-Trondheim", "config" : "goodlife","max-capacity": 1000, "available-capacity": 1000                                                           }
      ]
    }
}
"""


TEST_PATH_1 = {
    'source_network'  : 'Denmark',  'source_endpoint' : 'DK-Tjele',
    'dest_network'    : 'Sweden',   'dest_endpoint'   : 'SE-NSC',
    'paths'           :  [ [ nsa.SDP( nsa.STP('Denmark', 'DK-Saeby'), nsa.STP('Sweden', 'SE-Goteborg') ) ],
                           [ nsa.SDP( nsa.STP('Denmark', 'DK-Orestad'),       nsa.STP('Sweden', 'SE-Malmo') )    ]
                         ]
}

TEST_PATH_2 = {
    'source_network'  : 'Norway',   'source_endpoint' : 'NO-Trondheim',
    'dest_network'    : 'Sweden',   'dest_endpoint'   : 'SE-NSC',
    'paths'           : [ [ nsa.SDP( nsa.STP('Norway', 'NO-Fevik'),  nsa.STP('Denmark', 'DK-Hirtshals') ),
                            nsa.SDP( nsa.STP('Denmark', 'DK-Saeby'), nsa.STP('Sweden', 'SE-Goteborg') )
                          ],
                          [ nsa.SDP( nsa.STP('Norway', 'NO-Fevik'),  nsa.STP('Denmark', 'DK-Hirtshals') ),
                            nsa.SDP( nsa.STP('Denmark', 'DK-Orestad'),       nsa.STP('Sweden', 'SE-Malmo') )
                          ]
                        ]
}

TEST_PATH_3 = {
    'source_network'  : 'Denmark',  'source_endpoint' : 'DK-Tjele',
    'dest_network'    : 'Sweden',   'dest_endpoint'   : 'SE-NSC',
    'paths'           :  [ [ nsa.SDP( nsa.STP('Denmark', 'DK-Orestad'), nsa.STP('Sweden', 'SE-Malmo') ) ] ],
    'bandwidth'       : nsa.BandwidthParameters(1000, 1000, 1000)
}

TEST_PATHS = [ TEST_PATH_1, TEST_PATH_2, TEST_PATH_3 ]



class TopologyTest(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass


    def testParseAndFindPath(self):

        t = topology.parseJSONTopology(TEST_TOPOLOGY_1)

        for ts in TEST_PATHS:
            source_stp = nsa.STP(ts['source_network'], ts['source_endpoint'])
            dest_stp   = nsa.STP(ts['dest_network'], ts['dest_endpoint'])
            paths = t.findPaths(source_stp, dest_stp, ts.get('bandwidth'))
            for path in paths:
                self.assertEquals(ts['source_network'],  path.source_stp.network)
                self.assertEquals(ts['source_endpoint'], path.source_stp.endpoint)
                self.assertEquals(ts['dest_network'],    path.dest_stp.network)
                self.assertEquals(ts['dest_endpoint'],   path.dest_stp.endpoint)

            leps = [ path.endpoint_pairs for path in paths ]

            for p in ts['paths']:
                self.assertIn(p, leps)

