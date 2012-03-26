"""
Gole topology parser.

Author: Henrik Thostrup Jensen <htj@nordu.net>
        Jeroen van der Ham <vdham@uva.nl>

Copyright: NORDUnet (2011-2012)
"""

import re
import StringIO
from xml.etree import ElementTree as ET

from twisted.python import log

from opennsa import nsa, error
from opennsa.topology import topology


LOG_SYSTEM = 'opennsa.gole'


# Constants for parsing GOLE topology format
RDF_SCHEMA_NS   = 'http://www.w3.org/2000/01/rdf-schema#'
RDF_SYNTAX_NS   = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
OWL_NS          = 'http://www.w3.org/2002/07/owl#'
DTOX_NS         = 'http://www.glif.is/working-groups/tech/dtox#'


RDF_ABOUT               = '{%s}about'      % RDF_SYNTAX_NS
RDF_TYPE                = '{%s}type'       % RDF_SYNTAX_NS
RDF_RESOURCE            = '{%s}resource'   % RDF_SYNTAX_NS

RDF_COMMENT             = '{%s}comment'    % RDF_SCHEMA_NS
RDF_LABEL               = '{%s}label'      % RDF_SCHEMA_NS

NAMED_INDIVIDUAL        = '{%s}NamedIndividual' % OWL_NS

GLIF_HAS_STP            = '{%s}hasSTP'             % DTOX_NS
GLIF_CONNECTED_TO       = '{%s}connectedTo'        % DTOX_NS
GLIF_MAPS_TO            = '{%s}mapsTo'             % DTOX_NS
GLIF_MAX_CAPACITY       = '{%s}maxCapacity'        % DTOX_NS
GLIF_AVAILABLE_CAPACITY = '{%s}availableCapacity'  % DTOX_NS
GLIF_MANAGING           = '{%s}managing'           % DTOX_NS
GLIF_MANAGED_BY         = '{%s}managedBy'          % DTOX_NS
GLIF_LOCATED_AT         = '{%s}locatedAt'          % DTOX_NS
GLIF_LATITUDE           = '{%s}lat'                % DTOX_NS
GLIF_LONGITUDE          = '{%s}long'               % DTOX_NS
GLIF_ADMIN_CONTACT      = '{%s}adminContact'       % DTOX_NS
GLIF_PROVIDER_ENDPOINT  = '{%s}csProviderEndpoint' % DTOX_NS

GLIF_NETWORK            = DTOX_NS + 'NSNetwork'

NSNETWORK_PREFIX = 'urn:ogf:network:nsnetwork:'
NSA_PREFIX       = 'urn:ogf:network:nsa:'
STP_PREFIX       = 'urn:ogf:network:stp:'
STP_PLAIN_PREFIX = 'stp:'



def _stripPrefix(text, prefix):
    assert text.startswith(prefix), 'Text did not start with specified prefix (text: %s, prefix: %s)' % (text, prefix)
    ul = len(prefix)
    return text[ul:]



def _parseOWLTopology(topology_source):

    if isinstance(topology_source, file) or isinstance(topology_source, StringIO.StringIO):
        doc = ET.parse(topology_source)
    elif isinstance(topology_source, str):
        doc = ET.fromstring(topology_source)
    else:
        raise error.TopologyError('Invalid topology source')

    triples = set()

    root = doc.getroot()
    for e in root.getchildren():

        if e.tag == NAMED_INDIVIDUAL:
            resource = e.attrib[RDF_ABOUT]
            for el in e.getchildren():
                if   el.tag == RDF_TYPE:                triples.add( (resource, str(RDF_TYPE),           el.attrib.values()[0]) )
                elif el.tag == RDF_LABEL:               triples.add( (resource, str(RDF_LABEL),          el.text) )
                elif el.tag == GLIF_CONNECTED_TO:       triples.add( (resource, str(GLIF_CONNECTED_TO),  el.attrib.values()[0]) )
                elif el.tag == GLIF_HAS_STP:            triples.add( (resource, str(GLIF_HAS_STP),       el.attrib.values()[0]) )
                elif el.tag == GLIF_MAPS_TO:            triples.add( (resource, str(GLIF_MAPS_TO),       el.text or el.attrib.values()[0]) )
                elif el.tag == GLIF_PROVIDER_ENDPOINT:  triples.add( (resource, str(GLIF_PROVIDER_ENDPOINT), el.text) )
                elif el.tag == GLIF_MANAGED_BY:         triples.add( (resource, str(GLIF_MANAGED_BY),    el.attrib.values()[0]) )
                # We don't care about these
                elif el.tag in (RDF_COMMENT, GLIF_MANAGING, GLIF_ADMIN_CONTACT, GLIF_LOCATED_AT, GLIF_LATITUDE, GLIF_LONGITUDE):
                    pass
                else:
                    print 'Unknow tag type in topology: %s' % el.tag

    return triples



def _parseNRMMapping(nrm_mapping_source):

    if isinstance(nrm_mapping_source, file) or isinstance(nrm_mapping_source, StringIO.StringIO):
        source = nrm_mapping_source
    elif isinstance(nrm_mapping_source, str):
        from StringIO import StringIO
        source = StringIO(nrm_mapping_source)
    else:
        raise error.TopologyError('Invalid NRM Mapping Source')

    # regular expression for matching nrm mapping lines
    NRM_MAP_RX = re.compile('''\s*(.*)\s*"(.*)"''')

    triples = set()

    for line in source:
        line = line.strip()
        if line.startswith('#'):
            continue
        m = NRM_MAP_RX.match(line)
        if not m:
            continue
        stp, nrm_port = m.groups()
        stp = stp.strip()
        nrm_port = nrm_port.strip()
        if stp.startswith(STP_PREFIX):
            pass
        elif stp.startswith(STP_PLAIN_PREFIX):
            stp = 'urn:ogf:network:' + stp
        else:
            log.msg('Specifying STP without prefix is deprecated and support will be removed in a future version (STP %s)' % stp, system=LOG_SYSTEM)
            stp = STP_PREFIX + stp

        triples.add( (stp, str(GLIF_MAPS_TO), nrm_port ) )

    return triples



def parseTopology(topology_sources, nrm_mapping_source=None):

    triples = set()

    for ts in topology_sources:
        topo_triples = _parseOWLTopology(ts)
        triples = triples.union(topo_triples)

    if nrm_mapping_source:
        topo_triples = _parseNRMMapping(nrm_mapping_source)
        triples = triples.union(topo_triples)

    # extract topology from triples

    def getSubject(pred, obj):
        return [ t[0] for t in triples if t[1] == pred and t[2] == obj ]

    def getObjects(subj, pred):
        return [ t[2] for t in triples if t[0] == subj and t[1] == pred ]

    topo = topology.Topology()

    networks = getSubject(RDF_TYPE, GLIF_NETWORK)

    for network in networks:

        nsas      = getObjects(network, GLIF_MANAGED_BY)
        endpoints = getObjects(nsas[0], GLIF_PROVIDER_ENDPOINT)

        t_network_name  = _stripPrefix(network, NSNETWORK_PREFIX)
        t_nsa_name      = _stripPrefix(nsas[0], NSA_PREFIX)
        t_nsa_endpoint  = endpoints[0]

        t_network_nsa = nsa.NetworkServiceAgent(t_nsa_name, t_nsa_endpoint)
        t_network = nsa.Network(t_network_name, t_network_nsa)

        stps = getObjects(network, GLIF_HAS_STP)
        for stp in stps:
            t_stp_name = _stripPrefix(stp, STP_PREFIX).split(':')[-1]

            maps_to = getObjects(stp, GLIF_MAPS_TO)
            t_maps_to = maps_to[0] if maps_to else None

            dest_stps = getObjects(stp, GLIF_CONNECTED_TO)
            if dest_stps:
                dest_network, dest_port = _stripPrefix(dest_stps[0], STP_PREFIX).split(':',1)
                t_dest_stp = nsa.STP(dest_network, dest_port)
            else:
                t_dest_stp = None

            ep = nsa.NetworkEndpoint(t_network_name, t_stp_name, t_maps_to, t_dest_stp, None, None)
            t_network.addEndpoint(ep)

        topo.addNetwork(t_network)

    return topo

