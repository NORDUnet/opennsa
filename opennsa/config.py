"""
Configuration reader and defaults.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import ConfigParser



# defaults
DEFAULT_CONFIG_FILE     = '/etc/opennsa.conf'
DEFAULT_LOG_FILE        = '/var/log/opennsa.log'
DEFAULT_TLS             = 'true'
DEFAULT_TOPOLOGY_FILE   = '/usr/share/nsi/topology.owl'
DEFAULT_WSDL_DIRECTORY  = '/usr/share/nsi/wsdl'
DEFAULT_TCP_PORT        = 9080
DEFAULT_TLS_PORT        = 9443
DEFAULT_VERIFY          = 'true'


# config blocks and options
BLOCK_SERVICE    = 'service'
BLOCK_DUD        = 'dud'
BLOCK_JUNOS      = 'junos'
BLOCK_FORCE10    = 'force10'
BLOCK_ARGIA      = 'argia'

# service block
CONFIG_NETWORK_NAME     = 'network'     # mandatory
CONFIG_LOG_FILE         = 'logfile'
CONFIG_HOST             = 'host'
CONFIG_PORT             = 'port'
CONFIG_TLS              = 'tls'
CONFIG_TOPOLOGY_FILE    = 'topology'
CONFIG_NRM_MAP_FILE     = 'nrmmap'
CONFIG_WSDL_DIRECTORY   = 'wsdl'

CONFIG_HOSTKEY          = 'hostkey'     # mandatory, if tls is set
CONFIG_HOSTCERT         = 'hostcert'    # mandatory, if tls is set
CONFIG_CERTIFICATE_DIR  = 'certdir'     # mandatory (but dir can be empty)
CONFIG_VERIFY           = 'verify'

# generic ssh stuff, don't use directly
_SSH_HOST               = 'host'
_SSH_PORT               = 'port'
_SSH_HOST_FINGERPRINT   = 'fingerprint'
_SSH_USER               = 'user'
_SSH_PUBLIC_KEY         = 'publickey'
_SSH_PRIVATE_KEY        = 'privatekey'

# junos block
JUNOS_HOST              = _SSH_HOST
JUNOS_PORT              = _SSH_PORT
JUNOS_HOST_FINGERPRINT  = _SSH_HOST_FINGERPRINT
JUNOS_USER              = _SSH_USER
JUNOS_SSH_PUBLIC_KEY    = _SSH_PUBLIC_KEY
JUNOS_SSH_PRIVATE_KEY   = _SSH_PRIVATE_KEY

# force10 block
FORCE10_HOST            = _SSH_HOST
FORCE10_PORT            = _SSH_PORT
FORCE10_USER            = _SSH_USER
FORCE10_HOST_FINGERPRINT = _SSH_HOST_FINGERPRINT
FORCE10_SSH_PUBLIC_KEY  = _SSH_PUBLIC_KEY
FORCE10_SSH_PRIVATE_KEY = _SSH_PRIVATE_KEY

# argia block
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

