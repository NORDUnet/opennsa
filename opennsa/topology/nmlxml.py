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

    inbound_ports = []
    outbound_ports = []

    portName = lambda port : URN_NETWORK + ':' + port.name

    def addPort(port):
        #port_id = URN_NETWORK + ':' + port.name
        pn = ET.SubElement(topology, NML_PORT, {ID: portName(port) } )
        for label in port.labels():
            ln = ET.SubElement(pn, NML_LABEL, { LABEL_TYPE : label.type_} )
            ln.text = label.labelValue()
        if port.remote_network is not None:
            pr = ET.SubElement(pn, NML_RELATION, { TYPE : NML_ISALIAS} )
            pp = ET.SubElement(pr, NML_PORT, { ID : URN_OGF_NETWORK + port.remote_network + ':' + port.remote_port})

    # ports
    for port in network.inbound_ports:
        addPort(port)
        inbound_ports.append( portName( port ) )

    for port in network.outbound_ports:
        addPort(port)
        outbound_ports.append( portName( port ) )

    for port in network.bidirectional_ports:
        pn = ET.SubElement(topology, NML_BIDIRECTIONALPORT, { ID: portName(port) } )
        ET.SubElement(pn, NML_NAME).text = port.name
        ET.SubElement(pn, NML_PORT, {ID: URN_NETWORK + ':' + port.inbound_port.name} )
        ET.SubElement(pn, NML_PORT, {ID: URN_NETWORK + ':' + port.outbound_port.name} )
#        # add stuff about ports
#    else:
#            raise AssertionError('NML Port is not Port or BidirectionalPort')

    # node
    node = ET.SubElement(topology, NML_NODE, {ID: URN_NETWORK + ':node'})

    inbound_ports_ele  = ET.SubElement(node, NML_RELATION, {TYPE : NML_HASINBOUNDPORT} )
    outbound_ports_ele = ET.SubElement(node, NML_RELATION, {TYPE : NML_HASOUTBOUNDPORT} )

    for ip in inbound_ports:
        ET.SubElement(inbound_ports_ele,  NML_PORT, {ID : ip})
    for op in inbound_ports:
        ET.SubElement(outbound_ports_ele, NML_PORT, {ID : op})

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



def xmlNML(source):

    def baseName(urn_id):
        assert urn_id.startswith(URN_OGF_NETWORK), 'Identifier %s must start with urn ogf network prefix' % urn_id
        base_name = urn_id[len(URN_OGF_NETWORK):]
        return base_name

    def portName(port_id, network_name):
        network_port_name = baseName(port_id)
        assert network_port_name.startswith(network_name), 'Port name %s must start with network name %s' % (network_port_name, network_name)
        port_name = network_port_name[len(network_name)+1:]
        return port_name
 

    tree = ET.parse(source)

    topology = tree.getroot()
    assert topology.tag == NML_TOPOLOGY, 'Top level container must be a topology'

    topology_id = topology.attrib[ID]
    version     = topology.attrib[VERSION]

    network_name = baseName(topology_id)

    ports = {}
    i_ports = [] # ids of inbound ports
    o_ports = [] # ids of outbound ports
    b_ports = []
    managing_nsa_id = None

    inbound_ports       = []
    outbound_ports      = []
    bidirectional_ports = []

    for el in topology:
        if el.tag == NML_PORT:
            port_id = el.attrib[ID]
            port_name = portName(port_id, network_name)

            labels = []
            remote_network = None
            remote_port    = None
            for pel in el:
                if pel.tag == NML_LABEL:
                    label_type = pel.attrib[LABEL_TYPE]
                    label_value = pel.text
                    labels.append( nsa.Label(label_type, label_value) )
                elif pel.tag == NML_RELATION:
                    if pel.attrib[TYPE] == NML_ISALIAS:
                        port_alias = pel[0].attrib[ID]
                        network_port_name = baseName(port_alias)
                        remote_network, remote_port = network_port_name.rsplit(':',1)
                    else:
                        print "Unknown nml relation type %s" % pel.attrib[TYPE]
                else:
                    print "Unknown port element", pel
            port = nml.Port(port_name, labels, remote_network, remote_port)
            ports[port_name] = port

        elif el.tag == NML_BIDIRECTIONALPORT:
            sub_ports = []
            for pel in el:
                if pel.tag == NML_NAME:
                    name = pel.text
                elif pel.tag == NML_PORT:
                    sub_ports.append( pel.attrib[ID] )
            assert len(sub_ports) == 2, 'The number of ports in a bidirectional port must be 2'
            b_ports.append( (name, sub_ports) )

        elif el.tag == NML_NODE:
            node_id = el.attrib[ID]
            for pel in el:
                if pel.tag == NML_RELATION:
                    if pel.attrib[TYPE] == NML_HASINBOUNDPORT:
                        for port in pel:
                            if port.tag == NML_PORT:
                                port_id = port.attrib[ID]
                                i_ports.append(port_id)
                                port_name = portName(port_id, network_name)
                                inbound_ports.append( ports[port_name] )
                            else:
                                print 'Unrecognized tag in inbound port relation'

                    elif pel.attrib[TYPE] == NML_HASOUTBOUNDPORT:
                        for port in pel:
                            if port.tag == NML_PORT:
                                port_id = port.attrib[ID]
                                o_ports.append(port_id)
                                port_name = portName(port_id, network_name)
                                outbound_ports.append( ports[port_name] )
                            else:
                                print 'Unrecognized tag in outbound port relation'

                    elif pel.attrib[TYPE] == NML_MANAGEDBY:
                        rel = pel[0]
                        if rel.tag == NSI_NSA:
                            managing_nsa_id = rel.attrib[ID]
                        else:
                            print 'Unrecognized tag in managed by relation'

        elif el.tag == NSI_NSA:
            nsa_id = el.attrib[ID]
            nsa_name = baseName(nsa_id)
            if nsa_id == managing_nsa_id:
                for pel in el:
                    if pel.tag == NML_RELATION:
                        if pel.attrib[TYPE] == NSI_CSPROVIDERENDPOINT:
                            managing_nsa = nsa.NetworkServiceAgent(nsa_name, pel.text)

        else:
            print "Unknown topology element", el

    # now we have inbound/outbound ports and can create the bidirectional ports
    for name, (p1, p2) in b_ports:
        if p1 in i_ports:
            in_port  = ports[ portName(p1, network_name) ]
            out_port = ports[ portName(p2, network_name) ]
        else:
            in_port  = ports[ portName(p2, network_name) ]
            out_port = ports[ portName(p1, network_name) ]
        bidirectional_ports.append( nml.BidirectionalPort(name, in_port, out_port) )

    network = nml.Network(network_name, managing_nsa, inbound_ports, outbound_ports, bidirectional_ports)
    return network

