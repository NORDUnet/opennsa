"""
Tests multiple OpenNSA instances to ensure that discovery/topology/integration
is working.

Also uses config files, to ensure that works as well.


"""

import json
import tempfile
import configparser

from twisted.internet import defer
from twisted.application import internet, service

from twisted.trial import unittest

from opennsa.config import Config
from opennsa import constants, config, setup, nsa
from opennsa.protocols.shared import httpclient
# from opennsa.protocols.nsi2 import requesterservice, requesterclient
from opennsa.protocols.nsi2 import requesterclient
from opennsa.discovery.bindings import discovery

from . import db

ARUBA_CONFIG = """
[service]
domain=aruba.net
logfile=
rest=true
host=localhost
port=4080
peers=http://localhost:4081/NSI/discovery.xml

database={database}
dbhost={dbhost}
dbuser={dbuser}
dbpassword={dbpassword}

tls=false
certdir=/etc/ssl/certs

[dud:ojs]
nrmmap={aruba_ojs_nrm}

[dud:san]
nrmmap={aruba_san_nrm}
"""

ARUBA_OJS_NRM = b"""
ethernet    ps      -                                   vlan:1780-1799,2000     1000    em0 -
ethernet    ps2     -                                   vlan:1780-1799          1000    em1 -
ethernet    san     aruba.net:san#ojs(-in|-out)         vlan:1780-1799          1000    em2 -
"""

ARUBA_SAN_NRM = b"""
ethernet    ps      -                                   vlan:1780-1799,2000     1000    em0 -
ethernet    ps2     -                                   vlan:1780-1799          1000    em1 -
ethernet    ojs     aruba.net:ojs#san(-in|-out)         vlan:1780-1799          1000    em2 -
ethernet    bon     bonaire.net:topology#arb(-in|-out)  vlan:1780-1799          1000    em3 -
"""

BONAIRE_CONFIG = """
[service]
domain=bonaire.net
logfile=
host=localhost
port=4081

peers=http://localhost:4080/NSI/discovery.xml

database={database}
dbhost={dbhost}
dbuser={dbuser}
dbpassword={dbpassword}

tls=false
certdir=/etc/ssl/certs

[dud:topology]
nrmmap={bonaire_nrm}
"""

BONAIRE_NRM = b"""
ethernet    ps      -                                   vlan:1780-1789      1000        em0         -
ethernet    ps2     -                                   vlan:1780-1789      1000        em0         -
ethernet    arb     aruba.net:san#bon(-in|-out)         vlan:1780-1799      1000        em3         -
ethernet    cur     curacao.net:topology#bon(-in|-out)  vlan:1780-1799      1000        em2         -
"""


class MultipleInstancesTestMultipleInstancesTest(unittest.TestCase):

    def load_config(self, buffer):
        cfgIns = Config.instance()

        try:
            cfgIns._instance.cfg = None
            cfgIns._instance.vc = None
        except:
            pass

        tmp = tempfile.NamedTemporaryFile('w+t')
        tmp.write(buffer)
        tmp.flush()
        cfg, vc = cfgIns.read_config(tmp.name)
        tmp.close()
        return cfg, vc

    def setUp(self):

        # database

        tc = json.load(open(db.CONFIG_FILE))
        self.database = tc['database']
        self.db_user = tc['user']
        self.db_password = tc['password']
        self.db_host = tc['hostname']

        # make temporary files for nrm map files

        aruba_ojs_nrm_file = tempfile.NamedTemporaryFile()
        aruba_ojs_nrm_file.write(ARUBA_OJS_NRM)
        aruba_ojs_nrm_file.flush()

        aruba_san_nrm_file = tempfile.NamedTemporaryFile()
        aruba_san_nrm_file.write(ARUBA_SAN_NRM)
        aruba_san_nrm_file.flush()

        bonaire_nrm_file = tempfile.NamedTemporaryFile()
        bonaire_nrm_file.write(ARUBA_SAN_NRM)
        bonaire_nrm_file.flush()

        # construct config files

        aruba_config = ARUBA_CONFIG.format(database=self.database,
                                           dbhost=self.db_host,
                                           dbuser=self.db_user,
                                           dbpassword=self.db_password,
                                           aruba_ojs_nrm=aruba_ojs_nrm_file.name,
                                           aruba_san_nrm=aruba_san_nrm_file.name)

        bonaire_config = BONAIRE_CONFIG.format(database=self.database,
                                               dbhost=self.db_host,
                                               dbuser=self.db_user,
                                               dbpassword=self.db_password,
                                               bonaire_nrm=bonaire_nrm_file.name)

        # parse and verify config
        aruba_cfg, aruba_vc = self.load_config(aruba_config)
        bonaire_cfg, bonaire_vc = self.load_config(bonaire_config)

        # setup service

        aruba_nsa_service = setup.OpenNSAService(aruba_vc)
        bonaire_nsa_service = setup.OpenNSAService(bonaire_vc)

        aruba_factory, _ = aruba_nsa_service.setupServiceFactory()
        bonaire_factory, _ = bonaire_nsa_service.setupServiceFactory()

        self.top_service = service.MultiService()

        internet.TCPServer(aruba_vc[config.PORT], aruba_factory).setServiceParent(self.top_service)
        internet.TCPServer(bonaire_vc[config.PORT], bonaire_factory).setServiceParent(self.top_service)

        return self.top_service.startService()

    def tearDown(self):

        return self.top_service.stopService()

    @defer.inlineCallbacks
    def testDiscovery(self):

        aruba_discovery_service = 'http://localhost:4080/NSI/discovery.xml'
        bonaire_discovery_service = 'http://localhost:4080/NSI/discovery.xml'

        requester_agent = nsa.NetworkServiceAgent('test-requester:nsa', 'dud_endpoint1')

        d = httpclient.httpRequest(aruba_discovery_service.encode('utf-8'), b'', {}, b'GET', timeout=10)
        aruba_discovery_doc = yield d
        aruba_discovery = discovery.parse(aruba_discovery_doc)

        # basic tests
        self.failUnlessEqual('urn:ogf:network:aruba.net:nsa', aruba_discovery.id_, 'nsa id seems to be wrong')
        self.failUnlessEqual(2, len(aruba_discovery.networkId), 'should have two networks')
        self.failUnlessIn('urn:ogf:network:aruba.net:san', aruba_discovery.networkId, 'missing network in discovery')
        self.failUnlessIn('urn:ogf:network:aruba.net:san', aruba_discovery.networkId, 'missing network in discovery')

        cs_service_url = None
        nml_topologies = []

        for intf in aruba_discovery.interface:
            if intf.type_ == constants.CS2_SERVICE_TYPE:
                cs_service_url = intf.href
            elif intf.type_ == constants.NML_SERVICE_TYPE:
                nml_topologies.append(intf.href)

        self.failIfEqual(cs_service_url, None, 'No service url found')

        # header = nsa.NSIHeader(requester_agent.urn(), aruba_discovery.id_)
        # header.newCorrelationId()

        # provider = requesterclient.RequesterClient(self.provider_agent.endpoint, self.requester_agent.endpoint)
        # response_cid = yield self.provider.reserve(self.header, None, None, None, self.criteria)
