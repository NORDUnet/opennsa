"""
discovery service module

mostly just a place to keep all the information regarding discovery, and export
it to xml

Author: Henrik Thostrup Jensen <htj _at_ nordu.net>
Copyright: NORDUnet (2014)
"""

from xml.etree import ElementTree as ET

from twisted.python import log

from opennsa import constants as cnt
from opennsa.shared import xmlhelper, modifiableresource
from opennsa.discovery.bindings import discovery
from opennsa.topology.nmlxml import _baseName # nasty but I need it


LOG_SYSTEM = "DiscoveryService"


ET.register_namespace('nsi', discovery.NSI_DISCOVERY_NS)
ET.register_namespace('gns', discovery.GNS_NS)



class DiscoveryService:

    def __init__(self, nsa_id, version=None, name=None, software_version=None, start_time=None,
                 network_ids=None, interfaces=None, features=None, provider_registry=None,
                 link_node=None, domain_aggregate=False):

        self.nsa_id                 = nsa_id                # string
        self.version                = version               # datetime
        self.name                   = name                  # string
        self.software_version       = software_version      # string
        self.start_time             = start_time            # datetime
        self.network_ids            = network_ids           # [ string ]
        self.interfaces             = interfaces            # [ (type, url, described_by) ]
        self.features               = features              # [ (type, value) ]
        self.provider_registry      = provider_registry     # provreg.ProviderRegistry
        self.link_node              = link_node             # linkvector.Graph
        self.domain_aggregate       = domain_aggregate      # boolean


    def xml(self):

        log.msg("Generating new discovery xml resource", debug=True, system=LOG_SYSTEM)

        # location not really supported yet
        interface_types = [ discovery.InterfaceType(i[0], i[1], i[2]) for i in self.interfaces ]
        feature_types   = [ discovery.FeatureType(f[0], f[1]) for f in self.features ]

        peers_with = self.provider_registry.providers.keys()
        try:
            peers_with.remove(self.nsa_id)
        except ValueError:
            pass # running in aggregeter-only mode

        other = None

        if self.domain_aggregate:
            network_ids = [ cnt.URN_OGF_PREFIX + node_name for node_name in self.link_node.nodes.keys() \
                              if node_name.endswith( _baseName(self.network_ids[0]) ) ]

            # remove nsa ids of proxy domains from peers_with
            for pw in reversed(peers_with):
                if _baseName(pw).endswith( _baseName(self.nsa_id) ):
                    peers_with.remove(pw)

        else:
            network_ids = self.network_ids

        nsa_element = discovery.NsaType(
            self.nsa_id,
            xmlhelper.createXMLTime(self.version),
            None,
            self.name,
            self.software_version,
            xmlhelper.createXMLTime(self.start_time),
            network_ids,
            interface_types,
            feature_types,
            peers_with,
            other,
           )

        e = nsa_element.xml(discovery.nsa)
        payload = ET.tostring(e, 'utf-8')
        return payload


    def resource(self):

        r = modifiableresource.ModifiableResource('DiscoveryService', 'application/xml')
        r.updateResource(self.xml())
        return r

