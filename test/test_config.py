from twisted.trial import unittest

import json
import tempfile
import configparser

from opennsa import config
from . import db


ARUBA_DUD_CONFIG = """
[service]
network=aruba.net
logfile=
rest=true
port=4080
nrmmap=/dev/null
peers=http://localhost:4081/NSI/discovery.xml

database=opennsa-aruba
dbuser=htj
dbpassword=htj

tls=false

[dud]
"""

ARUBA_MULTI_DUD_CONFIG = """
[service]
network=aruba.net
logfile=
rest=true
port=4080
nrmmap=/dev/null
peers=http://localhost:4081/NSI/discovery.xml

database={database}
dbhost={db_host}
dbuser={db_user}
dbpassword={db_password}

tls=false


[dud:ojs]
nrmmap={nrm_ojs}

[dud:san]
nrmmap={nrm_san}
"""

ARUBA_OJS_NRM_MAP = b"""
ethernet    ps      -                                   vlan:1780-1799,2000     1000    em0 -
ethernet    ps2     -                                   vlan:1780-1799          1000    em1 -
ethernet    san     aruba.net:san#arb(-in|-out)         vlan:1780-1799          1000    em2 -
ethernet    bon     bonaire.net:topology#arb(-in|-out)  vlan:1780-1799          1000    em3 -
"""

ARUBA_SAN_NRM_MAP = b"""
ethernet    ps      -                                   vlan:1780-1799,2000     1000    em0 -
ethernet    ps2     -                                   vlan:1780-1799          1000    em1 -
ethernet    ojs     aruba.net:ojs#arb(-in|-out)         vlan:1780-1799          1000    em2 -
ethernet    bon     bonaire.net:topology#arb(-in|-out)  vlan:1780-1799          1000    em3 -
"""


class ConfigTest(unittest.TestCase):


    def setUp(self):

        tc = json.load( open(db.CONFIG_FILE) )
        self.database    = tc['database']
        self.db_user     = tc['user']
        self.db_password = tc['password']
        self.db_host     = '127.0.0.1'


    def testConfigParsing(self):

        raw_cfg = configparser.SafeConfigParser()
        raw_cfg.read_string(ARUBA_DUD_CONFIG)

        cfg = config.readVerifyConfig(raw_cfg)


    def testConfigParsingMultiBackend(self):

        # make temporary files for nrm map files

        aruba_ojs = tempfile.NamedTemporaryFile()
        aruba_ojs.write(ARUBA_OJS_NRM_MAP)
        aruba_ojs.flush()

        aruba_san = tempfile.NamedTemporaryFile()
        aruba_san.write(ARUBA_SAN_NRM_MAP)
        aruba_san.flush()

        # construct config file

        config_file_content = ARUBA_MULTI_DUD_CONFIG.format(database=self.database,
                                                            db_host=self.db_host,
                                                            db_user=self.db_user,
                                                            db_password=self.db_password,
                                                            nrm_ojs=aruba_ojs.name,
                                                            nrm_san=aruba_san.name)
        #print(config_file_content)

        # parse and verify config

        cfg = configparser.SafeConfigParser()
        cfg.read_string(config_file_content)

        verified_config = config.readVerifyConfig(cfg)

        print('')
        print('')

        #import pprint
        #pprint.pprint(verified_config)

        # This is not well suited for testing currently.. working on it
        from opennsa import setup
        nsa_service = setup.OpenNSAService(verified_config)
        nsa_service.startService()

