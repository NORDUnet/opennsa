"""
HTTP interface for retrieving a topology.

Currently this means an XML representation of an NML topology.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2013)
"""
from xml.etree import ElementTree as ET

from opennsa.shared import modifiableresource
from opennsa.topology import nmlxml



class NMLService(object):

    def __init__(self, nml_network):

        self.nml_network = nml_network
        self._resource = modifiableresource.ModifiableResource('NMLService', 'application/xml')
        self.update()


    def update(self):

        xml_nml_topology = nmlxml.topologyXML(self.nml_network)
        representation = ET.tostring(xml_nml_topology, 'utf-8')
        self._resource.updateResource(representation)


    def resource(self):

        return self._resource

