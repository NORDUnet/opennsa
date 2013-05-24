"""
HTTP interface for retrieving a topology.

Currently this means an XML representation of an NML topology.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2013)
"""
from xml.etree import ElementTree as ET

from twisted.python import log
from twisted.web import resource

from opennsa.topology import nmlxml



LOG_SYSTEM = 'topology.http'


class TopologyResource(resource.Resource):

    isLeaf = True

    def __init__(self, nml_topology):
        resource.Resource.__init__(self)

        xml = nmlxml.nmlXML(nml_topology)
        self.topology_representation = ET.tostring(xml)


    def render_GET(self, request):

        # we don't do any checking here, just service the topology

        log.msg('Topology request from %s. Sending %i bytes' % (request.getClient(), len(self.topology_representation)), system=LOG_SYSTEM)

        return self.topology_representation

