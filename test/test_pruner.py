from twisted.trial import unittest

from opennsa import nsa
from opennsa.plugins import pruner



class PrunerTest(unittest.TestCase):

    # These test cases assume that the pruner has surfnet as a prune target

    def setUp(self):
        pruner.NETWORKS = [ 'surfnet.nl' ]


    def testPruningStart(self):

        sfn_link = nsa.Link( nsa.STP('surfnet.nl:1990:production7', 'ps',         nsa.Label('vlan', '1784')),
                             nsa.STP('surfnet.nl:1990:production7', 'sara-ndn1',  nsa.Label('vlan', '1780-1799')) )

        ndn_link = nsa.Link( nsa.STP('nordu.net:2013:topology',     'surfnet',    nsa.Label('vlan', '1784-1789')),
                             nsa.STP('nordu.net:2013:topology',     'deic1',      nsa.Label('vlan', '1784-1789')) )

        dec_link = nsa.Link( nsa.STP('deic.dk:2013:topology',       'ndn1',       nsa.Label('vlan', '1784-1789')),
                             nsa.STP('deic.dk:2013:topology',       'ps',         nsa.Label('vlan', '1784')) )

        path = [ sfn_link, ndn_link, dec_link ]
        pruned_path = pruner.pruneLabels(path)

        self.assertEquals(pruned_path[0].dst_stp.label.labelValue(), '1784')
        self.assertEquals(pruned_path[1].src_stp.label.labelValue(), '1784')


    def testPruningEnd(self):

        ndn_link = nsa.Link( nsa.STP('nordu.net:2013:topology',     'funet',      nsa.Label('vlan', '2031-2035')),
                             nsa.STP('nordu.net:2013:topology',     'surfnet',    nsa.Label('vlan', '2-4094')) )

        sfn_link = nsa.Link( nsa.STP('surfnet.nl:1990:production7', 'nordunet',   nsa.Label('vlan', '2-4094')),
                             nsa.STP('surfnet.nl:1990:production7', '19523',      nsa.Label('vlan', '2077')) )

        path = [ ndn_link, sfn_link ]
        pruned_path = pruner.pruneLabels(path)

        self.assertEquals(pruned_path[0].dst_stp.label.labelValue(), '2077')
        self.assertEquals(pruned_path[1].src_stp.label.labelValue(), '2077')


