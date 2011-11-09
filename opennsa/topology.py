"""
OpenNSA topology database and parser.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2011)
"""

import json
import StringIO
from xml.etree import ElementTree as ET

import rdflib

from opennsa import nsa, error


# Constants for parsing GOLE topology format
OWL_NS  = 'http://www.w3.org/2002/07/owl#'
RDF_NS  = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'

GLIF_PREFIX = 'http://www.glif.is/working-groups/tech/dtox#'

NAMED_INDIVIDUAL        = ET.QName('{%s}NamedIndividual' % OWL_NS)
RDF_ABOUT               = ET.QName('{%s}about' % RDF_NS)
RDF_TYPE                = ET.QName('{%s}type' % RDF_NS)
RDF_RESOURCE            = ET.QName('{%s}resource' % RDF_NS)

GLIF_HAS_STP            = ET.QName('{%s}hasSTP' % GLIF_PREFIX)
GLIF_CONNECTED_TO       = ET.QName('{%s}connectedTo' % GLIF_PREFIX)
GLIF_MAPS_TO            = ET.QName('{%s}mapsTo' % GLIF_PREFIX)
GLIF_MAX_CAPACITY       = ET.QName('{%s}maxCapacity' % GLIF_PREFIX)
GLIF_AVAILABLE_CAPACITY = ET.QName('{%s}availableCapacity' % GLIF_PREFIX)
GLIF_MANAGED_BY         = ET.QName('{%s}managedBy' % GLIF_PREFIX)
GLIF_PROVIDER_ENDPOINT  = ET.QName('{%s}csProviderEndpoint' % GLIF_PREFIX)




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


    def getEndpoint(self, network, endpoint):

        nw = self.getNetwork(network)
        for ep in nw.endpoints:
            if ep.endpoint == endpoint:
                return ep


    def findPaths(self, source_stp, dest_stp, bandwidth=None):
        """
        Find possible paths between two endpoints.
        """
        # check that STPs exist
        snw = self.getNetwork(source_stp.network)
        sep = snw.getEndpoint(source_stp.endpoint)

        dnw = self.getNetwork(dest_stp.network)
        dep = dnw.getEndpoint(dest_stp.endpoint)

        # find endpoint pairs
        #print "FIND PATH", source_stp, dest_stp

        routes = self.findPathEndpoints(source_stp, dest_stp)
        if bandwidth is not None:
            routes = self.filterBandwidth(routes, bandwidth)

        # topology cannot represent vlans properly yet
        # this means that all ports can be matched with all ports internally in a network
        # this is incorrect if the network does not support vlan rewriting
        # currently only netherlight supports vlan rewriting (nov. 2011)
        routes = self._pruneMismatchedPorts(sep, dep, routes)

        paths = []
        if routes == []:
            paths.append( nsa.Path(sep, dep, []) )
        else:
            for sdps in routes:
                paths.append( nsa.Path(sep, dep, sdps ) )

        return paths


    def _pruneMismatchedPorts(self, source_ep, dest_ep, routes):

        valid_routes = []

        for path in routes:

            cur_source_ep = source_ep
            for sdp in path:
                cur_dest_ep = sdp.stp1
                assert cur_source_ep.network == cur_dest_ep.network, 'Cannot prune mismatched endpoint pairs %s %s' % (cur_source_ep, cur_dest_ep)
                source_vlan = cur_source_ep.endpoint.split('-')[-1]
                dest_vlan   = cur_dest_ep.endpoint.split('-')[-1]
                if cur_source_ep.network in ('netherlight.ets') or source_vlan == dest_vlan:
                    cur_source_ep = sdp.stp2
                    continue
                else:
                    break

            else: # loop did not break
                valid_routes.append(path)

        return valid_routes



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
                dest_ep = self.getEndpoint(ep.dest_stp.network, ep.dest_stp.endpoint)
                sp = nsa.SDP(ep, dest_ep)
                routes.append( [ sp ] )
            else:
                nvn = visited_networks[:] + [ ep.dest_stp.network ]
                subroutes = self.findPathEndpoints(ep.dest_stp, dest_stp, nvn)
                if subroutes:
                    for sr in subroutes:
                        src = sr[:]
                        dest_ep = self.getEndpoint(ep.dest_stp.network, ep.dest_stp.endpoint)
                        sp = nsa.SDP(ep, dest_ep)
                        src.insert(0, sp)
                        routes.append(  src  )

        return routes


    def filterBandwidth(self, paths_sdps, bandwidths):

        def hasBandwidth(route, bandwidths):
            for sdp in route:
                if sdp.stp1.available_capacity is not None and bandwidths.minimum is not None and sdp.stp1.available_capacity < bandwidths.minimum:
                    return False
                if sdp.stp2.available_capacity is not None and bandwidths.minimum is not None and sdp.stp2.available_capacity < bandwidths.minimum:
                    return False
            return True

        filtered_routes = [ route for route in paths_sdps if hasBandwidth(route, bandwidths) ]
        return filtered_routes


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
            ep = nsa.NetworkEndpoint(network_name, epd['name'], epd['config'], dest_stp, epd.get('max-capacity'), epd.get('available-capacity'))
            nw.addEndpoint(ep)

        topo.addNetwork(nw)

    return topo



def parseGOLETopology(topology_source):

    if isinstance(topology_source, file) or isinstance(topology_source, StringIO.StringIO):
        doc = ET.parse(topology_source)
    elif isinstance(topology_source, str):
        doc = ET.fromstring(topology_source)
    else:
        raise error.TopologyError('Invalid topology source')

    def stripGLIFPrefix(text):
        assert text.startswith(GLIF_PREFIX)
        return text.split(GLIF_PREFIX)[1]

    stps = {}
    nsas = {}
    networks = {}

    for e in doc.getiterator():

        if e.tag == NAMED_INDIVIDUAL:

            # determine indivdual (resource) type
            se = e.getiterator(RDF_TYPE)[0]
            rt = stripGLIFPrefix(se.attrib[RDF_RESOURCE])
            rt_name = e.attrib[RDF_ABOUT]

            if rt == 'STP':
                connected_to = None
                maps_to = None
                for ct in e.getiterator(GLIF_CONNECTED_TO):
                    connected_to = ct.attrib[RDF_RESOURCE]
                for ct in e.getiterator(GLIF_MAPS_TO):
                    maps_to = ct.attrib[RDF_RESOURCE]
                stps[rt_name] = { 'connected_to' : connected_to, 'maps_to' : maps_to }

            elif rt == 'NSNetwork':
                ns_stps = []
                for sse in e.getiterator(GLIF_HAS_STP):
                    ns_stps.append( sse.attrib[RDF_RESOURCE] )
                ns_nsa = None
                for mb in e.getiterator(GLIF_MANAGED_BY):
                    ns_nsa = mb.attrib[RDF_RESOURCE]
                networks[rt_name] = { 'stps': ns_stps, 'nsa' : ns_nsa }

            elif rt == 'NSA':
                endpoint = None
                for cpe in e.getiterator(GLIF_PROVIDER_ENDPOINT):
                    endpoint = cpe.text
                nsas[rt_name] = { 'endpoint' : endpoint }

            elif rt == 'Location':
                pass # we don't use that currently (in OpenNSA)

            else:
                print "Unknown Topology Resource", rt


    NSNETWORK_PREFIX = 'urn:ogf:network:nsnetwork:'
    NSA_PREFIX       = 'urn:ogf:network:nsa:'
    STP_PREFIX       = 'urn:ogf:network:stp:'

    def stripPrefix(text, prefix):
        assert text.startswith(prefix), 'Text did not start with specified prefix'
        ul = len(prefix)
        return text[ul:]


    topo = Topology()

    for network_name, network_params in networks.items():

        nsa_name     = network_params['nsa']
        nsa_endpoint = nsas[nsa_name].get('endpoint')

        t_network_name  = stripPrefix(network_name, NSNETWORK_PREFIX)
        t_nsa_name      = stripPrefix(nsa_name, NSA_PREFIX)

        network_nsa = nsa.NetworkServiceAgent(t_nsa_name, nsa_endpoint)
        network = nsa.Network(t_network_name, network_nsa)

        for stp_name in network_params['stps']:
            t_stp_name = stripPrefix(stp_name, STP_PREFIX).split(':')[-1]
            maps_to = stps.get(stp_name,{}).get('maps_to')
            dest_stp = None
            dest_stp_urn = stps.get(stp_name,{}).get('connected_to')
            if dest_stp_urn:
                dest_network, dest_port = stripPrefix(dest_stp_urn, STP_PREFIX).split(':',1)
                dest_stp = nsa.STP(dest_network, dest_port)
            ep = nsa.NetworkEndpoint(t_network_name, t_stp_name, maps_to, dest_stp, None, None)
            network.addEndpoint(ep)

        topo.addNetwork(network)

    return topo



def parseGOLERDFTopology(topology_source):

    def stripURNPrefix(text):
        URN_PREFIX = 'urn:ogf:network:'
        assert text.startswith(URN_PREFIX)
        return text.split(':')[-1]

    OWL_NS = rdflib.namespace.Namespace("http://www.w3.org/2002/07/owl#")
    RDF_NS = rdflib.namespace.Namespace('http://www.w3.org/1999/02/22-rdf-syntax-ns#')
    DTOX_NS = rdflib.namespace.Namespace('http://www.glif.is/working-groups/tech/dtox#')

    graph = rdflib.ConjunctiveGraph()
    try:
        graph.parse(topology_source)
    except:
        raise error.TopologyError('Invalid topology source')

    topo = Topology()

    for nsnetwork in graph.subjects(RDF_NS['type'],DTOX_NS['NSNetwork']):
        # Setup the base network object, with NSA
        nsaId = graph.value(subject=nsnetwork, predicate=DTOX_NS['managedBy'])
        network_name = stripURNPrefix(str(nsnetwork))
        network_nsa_ep = graph.value(subject=nsaId, predicate=DTOX_NS['csProviderEndpoint'])
        network_nsa = nsa.NetworkServiceAgent(stripURNPrefix(str(nsaId)), str(network_nsa_ep))
        network = nsa.Network(network_name, network_nsa)

        # Add all the STPs and connections to the network
        for stp in graph.objects(nsnetwork, DTOX_NS['hasSTP']):
            stp_name = stripURNPrefix(str(stp))
            dest_stp = graph.value(subject=stp, predicate=DTOX_NS['connectedTo'])
            # If there is a destination, add that, otherwise the value stays None.
            if dest_stp:
                dest_network = graph.value(predicate=DTOX_NS['hasSTP'], object=dest_stp)
                dest_stp = nsa.STP(stripURNPrefix(str(dest_network)), stripURNPrefix(str(dest_stp)))
            ep = nsa.NetworkEndpoint(network_name, stp_name, None, dest_stp, None, None)
            network.addEndpoint(ep)

        topo.addNetwork(network)

    return topo


