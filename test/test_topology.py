from twisted.trial import unittest

from opennsa import nsa, topology


# Copy of the NSI Quad topology for the RIO plugfest
# Has been "minimized"
TEST_TOPOLOGY_GOLE  = """<?xml version="1.0"?>
<rdf:RDF xmlns="http://www.glif.is/working-groups/tech/dtox#"
     xml:base="http://www.glif.is/working-groups/tech/dtox"
     xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
     xmlns:Curacao="http://www.glif.is/working-groups/tech/dtox#Curacao:"
     xmlns:Bonaire="http://www.glif.is/working-groups/tech/dtox#Bonaire:"
     xmlns:Aruba="http://www.glif.is/working-groups/tech/dtox#Aruba:"
     xmlns:owl="http://www.w3.org/2002/07/owl#"
     xmlns:xsd="http://www.w3.org/2001/XMLSchema#"
     xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
     xmlns:dtox="http://www.glif.is/working-groups/tech/dtox#"
     xmlns:Dominica="http://www.glif.is/working-groups/tech/dtox#Dominica:">

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Aruba">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Node"/>
        <hasSwitchMatrix rdf:resource="http://www.glif.is/working-groups/tech/dtox#Aruba.XM"/>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Aruba.Loc">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#GOLE"/>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Aruba.XM">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#SwitchMatrix"/>
        <canSwap rdf:datatype="http://www.w3.org/2001/XMLSchema#string">yes</canSwap>
        <hasPort rdf:resource="http://www.glif.is/working-groups/tech/dtox#Aruba:Aiden"/>
        <hasPort rdf:resource="http://www.glif.is/working-groups/tech/dtox#Aruba:Amelia"/>
        <hasPort rdf:resource="http://www.glif.is/working-groups/tech/dtox#Aruba:Ashley"/>
        <hasPort rdf:resource="http://www.glif.is/working-groups/tech/dtox#Aruba:Axel"/>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Aruba:Aiden">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Port"/>
        <maxCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">500.0</maxCapacity>
        <availableCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">500.0</availableCapacity>
        <connectedTo rdf:datatype="http://www.w3.org/2001/XMLSchema#string">Bonaire:Brutus</connectedTo>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Aruba:Amelia">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Port"/>
        <connectedTo rdf:datatype="http://www.w3.org/2001/XMLSchema#string"></connectedTo>
        <maxCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</maxCapacity>
        <availableCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</availableCapacity>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Aruba:Ashley">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Port"/>
        <connectedTo rdf:datatype="http://www.w3.org/2001/XMLSchema#string"></connectedTo>
        <maxCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</maxCapacity>
        <availableCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</availableCapacity>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Aruba:Axel">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Port"/>
        <maxCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</maxCapacity>
        <availableCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</availableCapacity>
        <connectedTo rdf:datatype="http://www.w3.org/2001/XMLSchema#string">Dominica:Dirk</connectedTo>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Bonaire">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Node"/>
        <hasSwitchMatrix rdf:resource="http://www.glif.is/working-groups/tech/dtox#Bonaire.XM"/>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Bonaire.Loc">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#GOLE"/>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Bonaire.XM">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#SwitchMatrix"/>
        <canSwap rdf:datatype="http://www.w3.org/2001/XMLSchema#string">yes</canSwap>
        <hasPort rdf:resource="http://www.glif.is/working-groups/tech/dtox#Bonaire:Basil"/>
        <hasPort rdf:resource="http://www.glif.is/working-groups/tech/dtox#Bonaire:Betty"/>
        <hasPort rdf:resource="http://www.glif.is/working-groups/tech/dtox#Bonaire:Bjorn"/>
        <hasPort rdf:resource="http://www.glif.is/working-groups/tech/dtox#Bonaire:Brutus"/>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Bonaire:Basil">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Port"/>
        <connectedTo rdf:datatype="http://www.w3.org/2001/XMLSchema#string"></connectedTo>
        <maxCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</maxCapacity>
        <availableCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</availableCapacity>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Bonaire:Betty">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Port"/>
        <connectedTo rdf:datatype="http://www.w3.org/2001/XMLSchema#string"></connectedTo>
        <maxCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</maxCapacity>
        <availableCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</availableCapacity>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Bonaire:Bjorn">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Port"/>
        <availableCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</availableCapacity>
        <maxCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</maxCapacity>
        <connectedTo rdf:datatype="http://www.w3.org/2001/XMLSchema#string">Curacao:Cynthia</connectedTo>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Bonaire:Brutus">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Port"/>
        <availableCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">500.0</availableCapacity>
        <maxCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">500.0</maxCapacity>
        <connectedTo rdf:datatype="http://www.w3.org/2001/XMLSchema#string">Aruba:Aiden</connectedTo>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Curacao">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Node"/>
        <hasSwitchMatrix rdf:resource="http://www.glif.is/working-groups/tech/dtox#Curacao.XM"/>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Curacao.Loc">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#GOLE"/>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Curacao.XM">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#SwitchMatrix"/>
        <canSwap rdf:datatype="http://www.w3.org/2001/XMLSchema#string">yes</canSwap>
        <hasPort rdf:resource="http://www.glif.is/working-groups/tech/dtox#Curacao:Calista"/>
        <hasPort rdf:resource="http://www.glif.is/working-groups/tech/dtox#Curacao:Carter"/>
        <hasPort rdf:resource="http://www.glif.is/working-groups/tech/dtox#Curacao:Chuck"/>
        <hasPort rdf:resource="http://www.glif.is/working-groups/tech/dtox#Curacao:Cynthia"/>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Curacao:Calista">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Port"/>
        <connectedTo rdf:datatype="http://www.w3.org/2001/XMLSchema#string"></connectedTo>
        <availableCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</availableCapacity>
        <maxCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</maxCapacity>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Curacao:Carter">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Port"/>
        <availableCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</availableCapacity>
        <maxCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</maxCapacity>
        <connectedTo rdf:datatype="http://www.w3.org/2001/XMLSchema#string">Dominica:Drusilla</connectedTo>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Curacao:Chuck">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Port"/>
        <connectedTo rdf:datatype="http://www.w3.org/2001/XMLSchema#string"></connectedTo>
        <maxCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</maxCapacity>
        <availableCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</availableCapacity>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Curacao:Cynthia">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Port"/>
        <availableCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</availableCapacity>
        <maxCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</maxCapacity>
        <connectedTo rdf:datatype="http://www.w3.org/2001/XMLSchema#string">Bonaire:Bjorn</connectedTo>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Dominica">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Node"/>
        <hasSwitchMatrix rdf:resource="http://www.glif.is/working-groups/tech/dtox#Dominica.XM"/>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Dominica.Loc">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#GOLE"/>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Dominica.XM">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#SwitchMatrix"/>
        <canSwap rdf:datatype="http://www.w3.org/2001/XMLSchema#string">yes</canSwap>
        <hasPort rdf:resource="http://www.glif.is/working-groups/tech/dtox#Dominica:Daisy"/>
        <hasPort rdf:resource="http://www.glif.is/working-groups/tech/dtox#Dominica:Dirk"/>
        <hasPort rdf:resource="http://www.glif.is/working-groups/tech/dtox#Dominica:Dorte"/>
        <hasPort rdf:resource="http://www.glif.is/working-groups/tech/dtox#Dominica:Drusilla"/>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Dominica:Daisy">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Port"/>
        <connectedTo rdf:datatype="http://www.w3.org/2001/XMLSchema#string"></connectedTo>
        <availableCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</availableCapacity>
        <maxCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</maxCapacity>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Dominica:Dirk">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Port"/>
        <availableCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</availableCapacity>
        <maxCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</maxCapacity>
        <connectedTo rdf:datatype="http://www.w3.org/2001/XMLSchema#string">Aruba:Axel</connectedTo>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Dominica:Dorte">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Port"/>
        <connectedTo rdf:datatype="http://www.w3.org/2001/XMLSchema#string"></connectedTo>
        <availableCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</availableCapacity>
        <maxCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</maxCapacity>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Dominica:Drusilla">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Port"/>
        <maxCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</maxCapacity>
        <availableCapacity rdf:datatype="http://www.w3.org/2001/XMLSchema#float">1000.0</availableCapacity>
        <connectedTo rdf:datatype="http://www.w3.org/2001/XMLSchema#string">Curacao:Carter</connectedTo>
    </owl:NamedIndividual>

    <owl:NamedIndividual rdf:about="http://www.glif.is/working-groups/tech/dtox#Maui">
        <rdf:type rdf:resource="http://www.glif.is/working-groups/tech/dtox#Node"/>
    </owl:NamedIndividual>
</rdf:RDF>
"""


TEST_TOPOLOGY_JSON = """
{
  "Aruba" : {
    "address"   : "address-aruba",
    "endpoints" : [
      { "name" : "Aiden",   "config" : "-", "max-capacity":  500, "available-capacity":  500, "dest-network" : "Bonaire", "dest-ep" : "Brutus"  },
      { "name" : "Amelia",  "config" : "-", "max-capacity": 1000, "available-capacity": 1000  },
      { "name" : "Ashley",  "config" : "-", "max-capacity": 1000, "available-capacity": 1000  },
      { "name" : "Axel",    "config" : "-", "max-capacity": 1000, "available-capacity": 1000, "dest-network" : "Dominica", "dest-ep" : "Dirk"    }
    ]
  },

  "Bonaire" : {
    "address"   : "address-bonaire",
    "endpoints" : [
      { "name" : "Basil",   "config" : "-", "max-capacity": 1000, "available-capacity": 1000 },
      { "name" : "Bette",   "config" : "-", "max-capacity": 1000, "available-capacity": 1000 },
      { "name" : "Bjorn",   "config" : "-", "max-capacity": 1000, "available-capacity": 1000, "dest-network" : "Curacao", "dest-ep" : "Cynthia" },
      { "name" : "Brutus",  "config" : "-", "max-capacity":  500, "available-capacity":  500, "dest-network" : "Aruba"  , "dest-ep" : "Aiden"   }
    ]
  },

  "Curacao" : {
    "address"   : "address-curacao",
    "endpoints" : [
      { "name" : "Calista", "config" : "-", "max-capacity": 1000, "available-capacity": 1000 },
      { "name" : "Carter",  "config" : "-", "max-capacity": 1000, "available-capacity": 1000, "dest-network" : "Dominica",  "dest-ep" : "Drusilla"  },
      { "name" : "Chuck",   "config" : "-", "max-capacity": 1000, "available-capacity": 1000  },
      { "name" : "Cynthia", "config" : "-", "max-capacity": 1000, "available-capacity": 1000, "dest-network" : "Bonaire",   "dest-ep" : "Bjorn"     }
    ]
  },

  "Dominica" : {
    "address"   : "address-dominica",
    "endpoints" : [
      { "name" : "Daisy",   "config" : "-", "max-capacity": 1000, "available-capacity": 1000 },
      { "name" : "Dirk",    "config" : "-", "max-capacity": 1000, "available-capacity": 1000, "dest-network" : "Aruba",   "dest-ep" : "Axel"    },
      { "name" : "Dorte",   "config" : "-", "max-capacity": 1000, "available-capacity": 1000 },
      { "name" : "Drusilla","config" : "-", "max-capacity": 1000, "available-capacity": 1000, "dest-network" : "Curacao", "dest-ep" : "Carter"  }
    ]
  }

}
"""

STP_AIDEN   = nsa.STP('Aruba', 'Aiden')
STP_AXEL    = nsa.STP('Aruba', 'Axel')

STP_BRUTUS  = nsa.STP('Bonaire', 'Brutus')
STP_BJORN   = nsa.STP('Bonaire', 'Bjorn')

STP_CARTER  = nsa.STP('Curacao', 'Carter')
STP_CYNTHIA = nsa.STP('Curacao', 'Cynthia')

STP_DIRK    = nsa.STP('Dominica', 'Dirk')
STP_DRUSILLA= nsa.STP('Dominica', 'Drusilla')


TEST_PATH_1 = {
    'source_network'  : 'Aruba',    'source_endpoint' : 'Ashley',
    'dest_network'    : 'Curacao',  'dest_endpoint'   : 'Chuck',
    'paths'           :  [ [ nsa.SDP( STP_AIDEN, STP_BRUTUS ), nsa.SDP( STP_BJORN, STP_CYNTHIA )   ],
                           [ nsa.SDP( STP_AXEL, STP_DIRK), nsa.SDP( STP_DRUSILLA, STP_CARTER )  ]
                         ]
}

TEST_PATH_2 = {
    'source_network'  : 'Aruba',    'source_endpoint' : 'Amelia',
    'dest_network'    : 'Bonaire',  'dest_endpoint'   : 'Bjorn',
    'paths'           : [ [ nsa.SDP( STP_AIDEN, STP_BRUTUS ) ],
                          [ nsa.SDP( STP_AXEL, STP_DIRK ), nsa.SDP(STP_DRUSILLA, STP_CARTER ), nsa.SDP(STP_CYNTHIA, STP_BJORN ) ] ]
}

TEST_PATH_3 = {
    'source_network'  : 'Aruba',    'source_endpoint' : 'Ashley',
    'dest_network'    : 'Bonaire',  'dest_endpoint'   : 'Basil',
    'paths'           :  [ [ nsa.SDP( STP_AXEL, STP_DIRK), nsa.SDP(STP_DRUSILLA, STP_CARTER), nsa.SDP(STP_CYNTHIA, STP_BJORN) ] ],
    'bandwidth'       : nsa.BandwidthParameters(1000, 1000, 1000)
}

TEST_PATHS = [ TEST_PATH_1, TEST_PATH_2, TEST_PATH_3 ]



class GenericTopologyTest:

    def testParseAndFindPath(self):

        for ts in TEST_PATHS:
            source_stp = nsa.STP(ts['source_network'], ts['source_endpoint'])
            dest_stp   = nsa.STP(ts['dest_network'], ts['dest_endpoint'])

            paths = self.topo.findPaths(source_stp, dest_stp, ts.get('bandwidth'))
            for path in paths:
                self.assertEquals(ts['source_network'],  path.source_stp.network)
                self.assertEquals(ts['source_endpoint'], path.source_stp.endpoint)
                self.assertEquals(ts['dest_network'],    path.dest_stp.network)
                self.assertEquals(ts['dest_endpoint'],   path.dest_stp.endpoint)

            leps = [ path.endpoint_pairs for path in paths ]

            self.assertEquals(len(leps), len(ts['paths']), 'Unexpected number of paths')
            for p in ts['paths']:
                self.assertIn(p, leps)



class GOLETopologyTest(GenericTopologyTest, unittest.TestCase):

    def setUp(self):
        self.topo = topology.parseGOLETopology(TEST_TOPOLOGY_GOLE)



class JSONTopologyTest(GenericTopologyTest, unittest.TestCase):

    def setUp(self):
        self.topo = topology.parseJSONTopology(TEST_TOPOLOGY_JSON)


