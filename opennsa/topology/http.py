"""
HTTP interface for retrieving a topology.

Currently this means an XML representation of an NML topology.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2013)
"""
import datetime
from xml.etree import ElementTree as ET

from twisted.python import log
from twisted.web import resource

from opennsa.topology import nmlxml



LOG_SYSTEM = 'topology.http'


class TopologyResource(resource.Resource):

    isLeaf = True

    RFC850_FORMAT       = '%a, %d %b %Y %H:%M:%S GMT'
    LAST_MODIFIED       = 'Last-modified'
    IF_MODIFIED_SINCE   = 'if-modified-since'

    def __init__(self, nsi_agent, nml_network):
        resource.Resource.__init__(self)

        self.nsi_agent   = nsi_agent
        self.nml_network = nml_network

        self.updateRepresentation()


    def updateRepresentation(self):
        xml = nmlxml.nsiXML(self.nsi_agent, self.nml_network)
        self.topology_representation = ET.tostring(xml)
        self.topology_version = self.nml_network.version.replace(microsecond=0)
        self.topology_version_http = datetime.datetime.strftime(self.nml_network.version, self.RFC850_FORMAT)


    def render_GET(self, request):

        # check for if-modified-since header, and send 304 back if it is not been modified
        msd_header = request.getHeader(self.IF_MODIFIED_SINCE)
        if msd_header:
            try:
                msd = datetime.datetime.strptime(msd_header, self.RFC850_FORMAT)
                if msd >= self.topology_version:
                    log.msg('Topology request from %s. Provided IMS %s (after last modification), sending 304 reply.' % (request.getClient(), msd_header), system=LOG_SYSTEM)
                    request.setResponseCode(304)
                    return ''
            except ValueError:
                pass # error parsing timestamp

        log.msg('Topology request from %s. Sending %i bytes' % (request.getClient(), len(self.topology_representation)), system=LOG_SYSTEM)

        request.setHeader(self.LAST_MODIFIED, self.topology_version_http)

        return self.topology_representation

