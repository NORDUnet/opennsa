from twisted.trial import unittest

import json
import tempfile
import configparser

from opennsa import config, setup
from . import db



ARUBA_DUD_CONFIG_NO_DATABASE = """
[service]
domain=aruba.net
logfile=
rest=true
port=4080

tls=false

[dud]
"""

ARUBA_DUD_CONFIG_NO_NETWORK_NAME = """
[service]
domain=aruba.net
logfile=
rest=true
port=4080
peers=http://localhost:4081/NSI/discovery.xml

database={database}
dbhost={db_host}
dbuser={db_user}
dbpassword={db_password}

tls=false

[dud]
"""

ARUBA_DUD_CONFIG = """
[service]
domain=aruba.net
logfile=
rest=true
port=4080
peers=http://localhost:4081/NSI/discovery.xml

database={database}
dbhost={db_host}
dbuser={db_user}
dbpassword={db_password}

tls=false

[dud:topology]
nrmmap={nrm_map}
"""

INVALID_LEGACY_CONFIG = """
[service]
network=aruba.net

[dud]
"""

ARUBA_MULTI_DUD_CONFIG = """
[service]
domain=aruba.net
logfile=
rest=true
port=4080
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


    def testConfigParsingNoDatabase(self):

        config_file_content = ARUBA_DUD_CONFIG_NO_DATABASE

        raw_cfg = configparser.SafeConfigParser()
        raw_cfg.read_string(config_file_content)

        try:
            cfg = config.readVerifyConfig(raw_cfg)
            nsa_service = setup.OpenNSAService(cfg)
            factory = nsa_service.setupServiceFactory()
            self.fail('Should have raised config.ConfigurationError')
        except config.ConfigurationError as e:
            pass


    def testConfigParsingNoNetworkName(self):

        config_file_content = ARUBA_DUD_CONFIG_NO_NETWORK_NAME.format(database=self.database,
                                                                      db_host=self.db_host,
                                                                      db_user=self.db_user,
                                                                      db_password=self.db_password)
        raw_cfg = configparser.SafeConfigParser()
        raw_cfg.read_string(config_file_content)

        try:
            cfg = config.readVerifyConfig(raw_cfg)
            nsa_service = setup.OpenNSAService(cfg)
            factory = nsa_service.setupServiceFactory()
            self.fail('Should have raised config.ConfigurationError')
        except config.ConfigurationError as e:
            pass


    def testConfigParsing(self):

        aruba_ojs = tempfile.NamedTemporaryFile()
        aruba_ojs.write(ARUBA_OJS_NRM_MAP)
        aruba_ojs.flush()

        config_file_content = ARUBA_DUD_CONFIG.format(database=self.database,
                                                      db_host=self.db_host,
                                                      db_user=self.db_user,
                                                      db_password=self.db_password,
                                                      nrm_map=aruba_ojs.name)

        raw_cfg = configparser.SafeConfigParser()
        raw_cfg.read_string(config_file_content)

        cfg = config.readVerifyConfig(raw_cfg)
        nsa_service = setup.OpenNSAService(cfg)
        factory = nsa_service.setupServiceFactory()


    def testInvalidLegacyConfig(self):

        raw_cfg = configparser.SafeConfigParser()
        raw_cfg.read_string(INVALID_LEGACY_CONFIG)
        try:
            cfg = config.readVerifyConfig(raw_cfg)
            self.fail('Should have raised ConfigurationError')
        except config.ConfigurationError:
            pass


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
        # parse and verify config

        cfg = configparser.SafeConfigParser()
        cfg.read_string(config_file_content)

        verified_config = config.readVerifyConfig(cfg)

        # do the setup dance to see if all the wiring is working, but don't start anything
        nsa_service = setup.OpenNSAService(verified_config)
        factory = nsa_service.setupServiceFactory()

