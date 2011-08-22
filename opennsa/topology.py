"""
OpenNSA topology database and parser.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2011)
"""

import json
import StringIO
from xml.etree import ElementTree as ET

from opennsa import nsa, error


# Constants for parsing GOLE topology format
OWL_NS  = 'http://www.w3.org/2002/07/owl#'
RDF_NS  = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'

GLIF_PREFIX = 'http://www.glif.is/working-groups/tech/dtox#'

NAMED_INDIVIDUAL        = ET.QName('{%s}NamedIndividual' % OWL_NS)
RDF_ABOUT               = ET.QName('{%s}about' % RDF_NS)

GLIF_CONNECTED_TO       = ET.QName('{%s}connectedTo' % GLIF_PREFIX)
GLIF_MAX_CAPACITY       = ET.QName('{%s}maxCapacity' % GLIF_PREFIX)
GLIF_AVAILABLE_CAPACITY = ET.QName('{%s}availableCapacity' % GLIF_PREFIX)




class Topology:

    def __init__(self):
        self.networks = []


    def addNetwork(self, network):
        if network.name in [ n.name for n in self.networks ]:
            raise error.TopologyError('Network name must be unique (name: %s)' % network.name)

        self.networks.append(network)


    def getNetwork(self, network_name):
        for network in self.networks:
            if network.name == network_name:
                return network

        raise error.TopologyError('No network named %s' % network_name)


    def findPaths(self, source_stp, dest_stp, service_params=None):
        """
        Find possible paths between two STPs.
        """
        # check that STPs exist
        snw = self.getNetwork(source_stp.network)
        snw.getEndpoint(source_stp.endpoint)

        dnw = self.getNetwork(dest_stp.network)
        dnw.getEndpoint(dest_stp.endpoint)

        # find endpoint pairs
        #print "FIND PATH", source_stp, dest_stp

        path_sdps = self.findPathEndpoints(source_stp, dest_stp)

        paths = []
        for sdps in path_sdps:
            paths.append( nsa.Path(source_stp, dest_stp, sdps ) )

        return paths


    def findPathEndpoints(self, source_stp, dest_stp, visited_networks=None):

        #print "FIND PATH EPS", source_stp, visited_networks

        snw = self.getNetwork(source_stp.network)
        routes = []

        for ep in snw.endpoints:

            #print "  Path:", ep, " ", dest_stp

            if ep.dest_stp is None:
                #print "    Rejecting endpoint due to no pairing"
                continue

            if visited_networks is None:
                visited_networks = [ source_stp.network ]

            if ep.dest_stp.network in visited_networks:
                #print "    Rejecting endpoint due to loop"
                continue

            if ep.dest_stp.network == dest_stp.network:
                sp = nsa.SDP(ep, ep.dest_stp)
                routes.append( [ sp ] )
            else:
                nvn = visited_networks[:] + [ ep.dest_stp.network ]
                subroutes = self.findPathEndpoints(ep.dest_stp, dest_stp, nvn)
                if subroutes:
                    for sr in subroutes:
                        src = sr[:]
                        sp = nsa.SDP(ep, ep.dest_stp)
                        src.insert(0, sp)
                        routes.append(  src  )

        return routes


    def __str__(self):
        return '\n'.join( [ str(n) for n in self.networks ] )




def parseJSONTopology(topology_source):

    if isinstance(topology_source, file) or isinstance(topology_source, StringIO.StringIO):
        topology_data = json.load(topology_source)
    elif isinstance(topology_source, str):
        topology_data = json.loads(topology_source)
    else:
        raise error.TopologyError('Invalid topology source')

    topo = Topology()

    for network_name, network_info in topology_data.items():
        nn = nsa.NetworkServiceAgent(str(network_info['address']))
        nw = nsa.Network(network_name, nn)
        for epd in network_info.get('endpoints', []):
            dest_stp = None
            if 'dest-network' in epd and 'dest-ep' in epd:
                dest_stp = nsa.STP( epd['dest-network'], epd['dest-ep'] )
            ep = nsa.NetworkEndpoint(network_name, epd['name'], epd['config'], dest_stp)
            nw.addEndpoint(ep)

        topo.addNetwork(nw)



def parseGOLETopology(topology_source):

    # hack until we get nsa address into gole topology
    nsa_address = {
        'Aruba'     : 'http://localhost:9080/NSI/services/ConnectionService',
        'Bonaire'   : 'http://localhost:9081/NSI/services/ConnectionService',
        'Curacao'   : 'http://localhost:9082/NSI/services/ConnectionService',
        'Dominica'  : 'http://localhost:9083/NSI/services/ConnectionService'
    }

    if isinstance(topology_source, file) or isinstance(topology_source, StringIO.StringIO):
        doc = ET.parse(topology_source)
    elif isinstance(topology_source, str):
        doc = ET.fromstring(topology_source)
        topology_data = json.loads(topology_source)
    else:
        raise error.TopologyError('Invalid topology source')

    networks = {}

    for e in doc.iter():

        if e.tag == NAMED_INDIVIDUAL:

            # determine individual type
            ent = e.attrib[RDF_ABOUT]
            assert ent.startswith(GLIF_PREFIX)
            ent = ent.split(GLIF_PREFIX)[1]

            if '.' in ent: # Location, X-Matrix
                continue

            elif ':' in ent: # Port
                network, portname = ent.split(':', 2)
                dest_stp = None
                for ct in e.iter(GLIF_CONNECTED_TO):
                    dest = ct.text
                    if dest:
                        dest_network, dest_portname = dest.split(':', 2)
                        dest_stp = nsa.STP(dest_network, dest_portname)
                # FIXME extract bandwidth stuff
                endpoint = nsa.NetworkEndpoint(network, portname, None, dest_stp)

                networks[network].addEndpoint(endpoint)

            else: # network (node)
                networks[ent] = nsa.Network(ent, nsa.NetworkServiceAgent(nsa_address[ent]))

        #elif e.tag == GLIF_MAX_CAPACITY:
        #    current_port.max_capacity = int(e.text)
        #elif e.tag == GLIF_AVAILABLE_CAPACITY:
        #    current_port.available_capacity = int(e.text)

    topo = Topology()
    for network in networks.values():
        topo.addNetwork(network)

    return topo

