"""
discovery service module

mostly just a place to keep all the information regarding discovery, and export
it to xml

Author: Henrik Thostrup Jensen <htj _at_ nordu.net>
Copyright: NORDUnet (2014)
"""

from xml.etree import ElementTree as ET

from opennsa.shared import xmlhelper, modifiableresource
from opennsa.discovery.bindings import discovery


ET.register_namespace('nsi', discovery.NSI_DISCOVERY_NS)
ET.register_namespace('gns', discovery.GNS_NS)



class DiscoveryService:

    def __init__(self, nsa_id, version=None, name=None, software_version=None, start_time=None,
                 network_ids=None, interfaces=None, features=None, peers_with=None,
                 route_vectors=None):

        self.nsa_id                 = nsa_id                # string
        self.version                = version               # datetime
        self.name                   = name                  # string
        self.software_version       = software_version      # string
        self.start_time             = start_time            # datetime
        self.network_ids            = network_ids           # [ string ]
        self.interfaces             = interfaces            # [ (type, url, described_by) ]
        self.features               = features              # [ (type, value) ]
        self.peers_with             = peers_with            # [ string ]
        self.route_vectors          = route_vectors         # nmlgns.RouteVectors


    def xml(self):

        # location not really supported yet
        interface_types = [ discovery.InterfaceType(i[0], i[1], i[2]) for i in self.interfaces ]
        feature_types   = [ discovery.FeatureType(f[0], f[1]) for f in self.features ]
        other = discovery.HolderType( [ discovery.Topology(t,c) for (t,c) in self.route_vectors.listVectors().items() ] )

        nsa_element = discovery.NsaType(
            self.nsa_id,
            xmlhelper.createXMLTime(self.version),
            None,
            self.name,
            self.software_version,
            xmlhelper.createXMLTime(self.start_time),
            self.network_ids,
            interface_types,
            feature_types,
            self.peers_with,
            other,
           )

        e = nsa_element.xml(discovery.nsa)
        payload = ET.tostring(e, 'utf-8')
        return payload


    def resource(self):

        r = modifiableresource.ModifiableResource('DiscoveryService', 'application/xml')
        r.updateResource(self.xml())
        return r

