"""
NML -> XML converter

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2013)
"""

from xml.etree import ElementTree as ET
import datetime

from opennsa import nsa
from opennsa.topology import nml


URN_OGF_NETWORK = 'urn:ogf:network:'

NML_NS = 'http://schemas.ogf.org/nml/2012/10/base#'
NSI_NS = 'http://schemas.ogf.org/nsi/2013/03/topology#'
VC_NS  = 'urn:ietf:params:xml:ns:vcard-4.0'

ET.register_namespace('nml', NML_NS)
ET.register_namespace('nsi', NSI_NS)
ET.register_namespace('vc',  VC_NS)

ID = 'id'
VERSION = 'version'
TYPE = 'type'
LABEL_TYPE = 'labelType'

NML_TOPOLOGY            = ET.QName('{%s}Topology'   % NML_NS)
NML_PORT                = ET.QName('{%s}Port'       % NML_NS)
NML_LABEL               = ET.QName('{%s}Label'      % NML_NS)
NML_NAME                = ET.QName('{%s}Name'       % NML_NS)
NML_RELATION            = ET.QName('{%s}Relation'   % NML_NS)
NML_NODE                = ET.QName('{%s}Node'       % NML_NS)
NML_BIDIRECTIONALPORT   = ET.QName('{%s}BidirectionalPort'  % NML_NS)

# this is odd xml
NML_HASINBOUNDPORT      = NML_NS + 'hasInboundPort'
NML_HASOUTBOUNDPORT     = NML_NS + 'hasOutboundPort'
NML_MANAGEDBY           = NML_NS + 'managedBy'
NML_ISALIAS             = NML_NS + 'isAlias'

NSI_NSA                 = ET.QName('{%s}NSA'        % NSI_NS)

NSI_CSPROVIDERENDPOINT  = NSI_NS + 'csProviderEndpoint'
NSI_ADMINCONTACT        = NSI_NS + 'adminContact'

VC_VCARD                = ET.QName('{%s}vcard'  % VC_NS)
VC_FN                   = ET.QName('{%s}fn'     % VC_NS)
VC_TEXT                 = ET.QName('{%s}text'   % VC_NS)


def nmlXML(network):

    URN_NETWORK = URN_OGF_NETWORK + network.name

    utc_now = datetime.datetime.utcnow().isoformat() + 'Z'

    topology = ET.Element(NML_TOPOLOGY, {ID: URN_NETWORK, VERSION: utc_now } )

    # ports
    for port in network.ports:
        port_id = URN_NETWORK + ':' + port.name
        if isinstance(port, nml.Port):
            pn = ET.SubElement(topology, NML_PORT, {ID: port_id} )
            for label in port.labels():
                ln = ET.SubElement(pn, NML_LABEL, { LABEL_TYPE : label.type_} )
                ln.text = label.labelValue()
            if port.remote_network is not None:
                pr = ET.SubElement(pn, NML_RELATION, { TYPE : NML_ISALIAS} )
                pp = ET.SubElement(pr, NML_PORT, { ID : URN_OGF_NETWORK + port.remote_network + ':' + port.remote_port})
        elif isinstance(port, nml.BidirectionalPort):
            pn = ET.SubElement(topology, NML_BIDIRECTIONALPORT, { ID: port_id } )
            ET.SubElement(pn, NML_NAME).text = port.name
            ET.SubElement(pn, NML_PORT, {ID: URN_NETWORK + ':' + port.inbound_port.name} )
            ET.SubElement(pn, NML_PORT, {ID: URN_NETWORK + ':' + port.outbound_port.name} )
            # add stuff about ports
        else:
            raise AssertionError('NML Port is not Port or BidirectionalPort')

    # node
    node = ET.SubElement(topology, NML_NODE, {ID: URN_NETWORK + ':node'})

    inbound_ports  = ET.SubElement(node, NML_RELATION, {TYPE : NML_HASINBOUNDPORT} )
    outbound_ports = ET.SubElement(node, NML_RELATION, {TYPE : NML_HASOUTBOUNDPORT} )
    for port in network.ports:
        if isinstance(port, nml.Port):
            if port.orientation is nml.INGRESS:
                ET.SubElement(inbound_ports, NML_PORT, {ID : URN_NETWORK + ':' + port.name})
            else:
                ET.SubElement(outbound_ports, NML_PORT, {ID : URN_NETWORK + ':' + port.name})

    urn_nsa = URN_NETWORK + ':nsa'

    managed_by = ET.SubElement(node, NML_RELATION, { TYPE : NML_MANAGEDBY } )
    ET.SubElement(managed_by, NSI_NSA, {ID : urn_nsa})

    # nsa
    nsi_agent = ET.SubElement(topology, NSI_NSA, { ID : network.managing_nsa.urn() })
    ET.SubElement(nsi_agent, NML_RELATION, {TYPE: NSI_CSPROVIDERENDPOINT} ).text = network.managing_nsa.endpoint
    #vcard = ET.SubElement(nsi_agent, VC_VCARD)
    #fn    = ET.SubElement(vcard, VC_FN)
    #vtext = ET.SubElement(fn, VC_TEXT).text = "VCard Text goes here"

    return topology

