"""
NRM topology parser.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2011-2012)
"""

import re
import StringIO

from twisted.python import log

from opennsa import error


LOG_SYSTEM = 'topology.nrmparser'


BIDRECTIONAL_ETHERNET   = 'bi-ethernet'
UNIDIRECTIONAL_ETHERNET = 'uni-ethernet'

PORT_TYPES = [ BIDRECTIONAL_ETHERNET, UNIDIRECTIONAL_ETHERNET ]



class Label:

    def __init__(self, label):
        if '-' in label:
            self.start, self.stop = label.split('-',1)
        else:
            self.start, self.stop = label, label


    def __str__(self):
        return '<Label %s>' % ('%s-%s' % (self.start, self.stop) if self.start != self.stop else self.start)


    def __repr__(self):
        return str(self)



class NRMEntry:

    def __init__(self, port_type, port_name, remote_port, labels, interface):
        # port_type     : string
        # port_name     : string
        # remote_port   : (string, string)
        # labels        : {string: (label|label-range)}
        # interface     : string

        self.port_type  = port_type
        self.port_name  = port_name
        self.remote_port = remote_port
        self.labels     = labels
        self.interface  = interface


    def __str__(self):
        return '<NRMEntry: %s, %s, %s, %s, %s>' % (self.port_type, self.port_name, self.remote_port, self.labels, self.interface)



def parseTopologySpec(source):

    # Parse the entries like the following:

    ## type          name            remote                          labels              interface
    #
    #bi-ethernet     ps              -                               vlan:1780-1783      em0
    #bi-ethernet     netherlight     netherlight:nordu-netherlight   vlan:1780-1783      em1
    #bi-ethernet     uvalight        uvalight:uvalight               vlan:1780-1783      em2

    # Line starting with # and blank lines should be ignored

    assert isinstance(source, file) or isinstance(source, StringIO.StringIO), 'Topology source must be file or StringIO instance'

    TOPO_RX = re.compile('''(.+?)\s+(.+?)\s+(.+?)\s+(.+?)\s+(.+)''')

    entries = []

    for line in source:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        match = TOPO_RX.match(line)
        if not match:
            print "No match for entry: ", line

        else:
            port_type, port_name, remote_port, labels, interface = match.groups()

            if not port_type in PORT_TYPES:
                raise error.TopologyError('Port type %s is not a valid port type' % port_type)

            if remote_port == '-':
                remote_port = None

            label_entries = {}
            for l_entry in labels.split(','):
                if not ':' in l_entry:
                    raise error.TopologyError('Invalid label description: %s' % l_entry)
                label_type, label_range = l_entry.split(':')
                if label_type in label_entries:
                    raise error.TopologyError('Multiple labels for type %s' % label_type)
                label_entries[label_type] = Label(label_range)

            if interface.startswith('"') and interface.endswith('"'):
                interface = interface[1:-1]

            ne = NRMEntry(port_type, port_name, remote_port, label_entries, interface)
            entries.append(ne)

    # check for no entries?

    return entries



if __name__ == '__main__':

    entry = """bi-ethernet     ps              -                               vlan:1780-1783      em0
               bi-ethernet     netherlight     netherlight:ndn-netherlight     vlan:1780-1783      em1
               bi-ethernet     netherlight     netherlight:ndn-netherlight     vlan:1780-1783      "em 8"
               bi-ethernet     uvalight        uvalight:ndn-uvalight           vlan:1780-1783      em2"""

    source = StringIO.StringIO(entry)

    entries = parseTopologySpec(source)
    for e in entries:
        print e

