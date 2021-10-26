from twisted.trial import unittest

import json
import tempfile
import configparser
from io import StringIO

from opennsa import config, setup
from opennsa.config import Config
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

[backends:dummy]
name=foobar
"""

ARUBA_DUD_CONFIG = """
[service]
domain=aruba.net
host=dummy
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

    def _reset_instance(self):
        try:
            self.configIns._instance.cfg = None
            self.configIns._instance.vc = None
        except:
            pass

    def setUp(self):
        self.configIns = Config.instance()
        self._reset_instance()
        tc = json.load(open(db.CONFIG_FILE))
        self.database = tc['database']
        self.db_user = tc['user']
        self.db_password = tc['password']
        self.db_host = tc['hostname']

    def _generate_temp_file(self, buffer):
        """
        Helper utility to generate a temp file and write buffer to it.
        """
        tmp = tempfile.NamedTemporaryFile('w+t')
        tmp.write(buffer)
        tmp.flush()
        return tmp

    def testConfigParsingNoDatabase(self):

        config_file_content = ARUBA_DUD_CONFIG_NO_DATABASE

        expectedError = "No database specified in configuration file (mandatory)"
        tmp = None

        try:
            tmp = self._generate_temp_file(config_file_content)
            cfg, vc = self.configIns.read_config(tmp.name)
            nsa_service = setup.OpenNSAService(cfg)
            factory, _ = nsa_service.setupServiceFactory()
            self.fail('Should have raised config.ConfigurationError')
        except config.ConfigurationError as e:
            self.assertEquals(expectedError, e.args[0])
        finally:
            if tmp is not None:
                tmp.close()

    def testConfigParsingNoNetworkName(self):

        config_file_content = ARUBA_DUD_CONFIG_NO_NETWORK_NAME.format(database=self.database,
                                                                      db_host=self.db_host,
                                                                      db_user=self.db_user,
                                                                      db_password=self.db_password)
        tmp = None
        try:
            tmp = self._generate_temp_file(config_file_content)
            cfg, vc = self.configIns.read_config(tmp.name)
            nsa_service = setup.OpenNSAService(self.configIns.config_dict())
            factory, _ = nsa_service.setupServiceFactory()
            self.fail('Should have raised config.ConfigurationError')
        except config.ConfigurationError as e:
            pass
        finally:
            if tmp is not None:
                tmp.close()

    def testConfigParsing(self):

        aruba_ojs = tempfile.NamedTemporaryFile()
        aruba_ojs.write(ARUBA_OJS_NRM_MAP)
        aruba_ojs.flush()

        config_file_content = ARUBA_DUD_CONFIG.format(database=self.database,
                                                      db_host=self.db_host,
                                                      db_user=self.db_user,
                                                      db_password=self.db_password,
                                                      nrm_map=aruba_ojs.name)

        tmp = self._generate_temp_file(config_file_content)
        cfg, vc = self.configIns.read_config(tmp.name)

        try:
            nsa_service = setup.OpenNSAService(vc)
            factory, _ = nsa_service.setupServiceFactory()
        finally:
            tmp.close()
            aruba_ojs.close()

    def testInvalidLegacyConfig(self):

        config_file_content = INVALID_LEGACY_CONFIG
        tmp = self._generate_temp_file(config_file_content)

        try:
            cfg, vc = self.configIns.read_config(tmp.name)
            self.fail('Should have raised ConfigurationError')
        except config.ConfigurationError:
            pass
        finally:
            tmp.close()

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
        tmp = self._generate_temp_file(config_file_content)

        try:
            cfg, verified_config = self.configIns.read_config(tmp.name)

            # do the setup dance to see if all the wiring is working, but don't start anything
            nsa_service = setup.OpenNSAService(verified_config)
            factory, _ = nsa_service.setupServiceFactory()
        finally:
            tmp.close()
