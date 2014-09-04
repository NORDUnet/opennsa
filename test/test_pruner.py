from twisted.trial import unittest

from opennsa import nsa
from opennsa.plugins import pruner



class PrunerTest(unittest.TestCase):

    # These test cases assume that the pruner has surfnet as a prune target

    def testPruningStart(self):

        sfn_link = nsa.Link('surfnet.nl:1990:production7', 'ps', 'sara-ndn1',   nsa.Label('vlan', '1784'),      nsa.Label('vlan', '1780-1799') )
        ndn_link = nsa.Link('nordu.net:2013:topology', 'surfnet', 'deic1',      nsa.Label('vlan', '1780-1799'), nsa.Label('vlan', '1784-1789') )
        dec_link = nsa.Link('deic.dk:2013:topology', 'ndn1', 'ps',              nsa.Label('vlan', '1784-1789'), nsa.Label('vlan', '1784') )

        path = [ sfn_link, ndn_link, dec_link ]
        pruned_path = pruner.pruneLabels(path)

        self.assertEquals(pruned_path[0].dst_label.labelValue(), '1784')
        self.assertEquals(pruned_path[1].src_label.labelValue(), '1784')


    def testPruningEnd(self):

        ndn_link = nsa.Link('nordu.net:2013:topology', 'funet', 'surfnet',      nsa.Label('vlan', '2031-2035'), nsa.Label('vlan', '2-4094'))
        sfn_link = nsa.Link('surfnet.nl:1990:production7', 'nordunet', '19523', nsa.Label('vlan', '2-4094'),    nsa.Label('vlan', '2077'))

        path = [ ndn_link, sfn_link ]
        pruned_path = pruner.pruneLabels(path)

        self.assertEquals(pruned_path[0].dst_label.labelValue(), '2077')
        self.assertEquals(pruned_path[1].src_label.labelValue(), '2077')


