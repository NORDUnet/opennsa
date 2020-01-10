from twisted.trial import unittest

import configparser

from opennsa import config


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


class ConfigTest(unittest.TestCase):


    def testConfigParsing(self):

        raw_cfg = configparser.SafeConfigParser()
        raw_cfg.read_string(ARUBA_DUD_CONFIG)

        cfg = config.readVerifyConfig(raw_cfg)

