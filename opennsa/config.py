"""
Configuration reader and defaults.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import ConfigParser



# defaults
DEFAULT_CONFIG_FILE     = '/etc/opennsa.conf'
DEFAULT_LOG_FILE        = '/var/log/opennsa.log'
DEFAULT_TOPOLOGY_FILE   = '/usr/share/nsi/topology.owl'
DEFAULT_WSDL_DIRECTORY  = '/usr/share/nsi/wsdl'
DEFAULT_TCP_PORT        = 9080
DEFAULT_TLS_PORT        = 9443
DEFAULT_VERIFY          = 'true'


# config blocks and options
BLOCK_SERVICE    = 'service'
BLOCK_DUD        = 'dud'
BLOCK_JUNOS      = 'junos'
BLOCK_ARGIA      = 'argia'

# service block
CONFIG_NETWORK_NAME     = 'network'     # mandatory
CONFIG_LOG_FILE         = 'logfile'
CONFIG_HOST             = 'host'
CONFIG_PORT             = 'port'
CONFIG_TOPOLOGY_FILE    = 'topology'
CONFIG_WSDL_DIRECTORY   = 'wsdl'

CONFIG_HOSTKEY          = 'hostkey'     # mandatory
CONFIG_HOSTCERT         = 'hostcert'    # mandatory
CONFIG_CERTIFICATE_DIR  = 'certdir'     # mandatory (but dir can be empty)
CONFIG_VERIFY           = 'verify'

ARGIA_COMMAND_DIR       = 'commanddir'
ARGIA_COMMAND_BIN       = 'commandbin'



def readConfig(filename):

    cfg = ConfigParser.SafeConfigParser()

    # add defaults, only section so far
    cfg.add_section(BLOCK_SERVICE)
    cfg.set(BLOCK_SERVICE, CONFIG_LOG_FILE,         DEFAULT_LOG_FILE)
    cfg.set(BLOCK_SERVICE, CONFIG_TOPOLOGY_FILE,    DEFAULT_TOPOLOGY_FILE)
    cfg.set(BLOCK_SERVICE, CONFIG_WSDL_DIRECTORY,   DEFAULT_WSDL_DIRECTORY)
    cfg.set(BLOCK_SERVICE, CONFIG_VERIFY,           DEFAULT_VERIFY)

    cfg.read( [ filename ] )

    return cfg

