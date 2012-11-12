"""
Configuration reader and defaults.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import os
import ConfigParser



# defaults
DEFAULT_CONFIG_FILE     = '/etc/opennsa.conf'
DEFAULT_LOG_FILE        = '/var/log/opennsa.log'
DEFAULT_TLS             = 'true'
DEFAULT_TOPOLOGY_FILE   = '/usr/local/share/nsi/topology.owl'
DEFAULT_WSDL_DIRECTORY  = '/usr/local/share/nsi/wsdl'
DEFAULT_TCP_PORT        = 9080
DEFAULT_TLS_PORT        = 9443
DEFAULT_VERIFY          = True


# config blocks and options
BLOCK_SERVICE    = 'service'
BLOCK_DUD        = 'dud'
BLOCK_JUNOS      = 'junos'
BLOCK_FORCE10    = 'force10'
BLOCK_ARGIA      = 'argia'
BLOCK_BROCADE    = 'brocade'

# service block
NETWORK_NAME     = 'network'     # mandatory
LOG_FILE         = 'logfile'
HOST             = 'host'
PORT             = 'port'
TLS              = 'tls'
TOPOLOGY_FILE    = 'topology'
NRM_MAP_FILE     = 'nrmmap'
WSDL_DIRECTORY   = 'wsdl'

KEY              = 'key'         # mandatory, if tls is set
CERTIFICATE      = 'certificate' # mandatory, if tls is set
CERTIFICATE_DIR  = 'certdir'     # mandatory (but dir can be empty)
VERIFY_CERT      = 'verify'

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

# Brocade block
BROCADE_HOST              = _SSH_HOST
BROCADE_PORT              = _SSH_PORT
BROCADE_HOST_FINGERPRINT  = _SSH_HOST_FINGERPRINT
BROCADE_USER              = _SSH_USER
BROCADE_SSH_PUBLIC_KEY    = _SSH_PUBLIC_KEY
BROCADE_SSH_PRIVATE_KEY   = _SSH_PRIVATE_KEY



class ConfigurationError(Exception):
    """
    Raised in case of invalid/inconsistent configuration.
    """


def readConfig(filename):

    cfg = ConfigParser.SafeConfigParser()

    cfg.add_section(BLOCK_SERVICE)
    cfg.read( [ filename ] )

    return cfg



def readVerifyConfig(cfg):
    """
    Read a config and verify that things are correct. Will also fill in
    default values where applicable.

    This is supposed to be used during application creation (before service
    start) to ensure that simple configuration errors do not pop up efter
    daemonization.

    Returns a "verified" config, which is a dictionary.
    """

    vc = {}

    try:
        vc[NETWORK_NAME] = cfg.get(BLOCK_SERVICE, NETWORK_NAME)
    except ConfigParser.NoOptionError:
        raise ConfigurationError('No network name specified in configuration file (mandatory)')

    try:
        vc[LOG_FILE] = cfg.get(BLOCK_SERVICE, LOG_FILE)
    except ConfigParser.NoOptionError:
        vc[LOG_FILE] = DEFAULT_LOG_FILE

    try:
        topology_list = cfg.get(BLOCK_SERVICE, TOPOLOGY_FILE)
    except ConfigParser.NoOptionError:
        topology_list = DEFAULT_TOPOLOGY_FILE
    topology_files = topology_list.split(',')
    for topology_file in topology_files:
        if not os.path.exists(topology_file):
            raise ConfigurationError('Specified (or default) topology file does not exist (%s)' % topology_file)
    vc[TOPOLOGY_FILE] = topology_files

    try:
        nrm_map_file = cfg.get(BLOCK_SERVICE, NRM_MAP_FILE)
        if not os.path.exists(nrm_map_file):
            raise ConfigurationError('Specified NRM mapping file does not exist (%s)' % nrm_map_file)
        vc[NRM_MAP_FILE] = nrm_map_file
    except ConfigParser.NoOptionError:
        vc[NRM_MAP_FILE] = None

    try:
        wsdl_dir = cfg.get(BLOCK_SERVICE, WSDL_DIRECTORY)
        if not os.path.exists(wsdl_dir):
            raise ConfigurationError('Specified (or default) WSDL directory does not exist (%s)' % wsdl_dir)
        vc[WSDL_DIRECTORY] = wsdl_dir
    except ConfigParser.NoOptionError:
        vc[WSDL_DIRECTORY] = DEFAULT_WSDL_DIRECTORY

    try:
        vc[HOST] = cfg.get(BLOCK_SERVICE, HOST)
    except ConfigParser.NoOptionError:
        vc[HOST] = None

    try:
        vc[TLS] = cfg.getboolean(BLOCK_SERVICE, TLS)
    except ConfigParser.NoOptionError:
        vc[TLS] = DEFAULT_TLS

    try:
        vc[PORT] = cfg.getint(BLOCK_SERVICE, PORT)
    except ConfigParser.NoOptionError:
        vc[PORT] = DEFAULT_TLS_PORT if vc[TLS] else DEFAULT_TCP_PORT

    if vc[TLS]:
        try:
            hostkey  = cfg.get(BLOCK_SERVICE, KEY)
            hostcert = cfg.get(BLOCK_SERVICE, CERTIFICATE)
            certdir  = cfg.get(BLOCK_SERVICE, CERTIFICATE_DIR)
            try:
                vc[VERIFY_CERT] = cfg.getboolean(BLOCK_SERVICE, VERIFY_CERT)
            except ConfigParser.NoOptionError:
                vc[VERIFY_CERT] = DEFAULT_VERIFY

            if not os.path.exists(hostkey):
                raise ConfigurationError('Specified hostkey does not exist (%s)' % hostkey)
            if not os.path.exists(hostcert):
                raise ConfigurationError('Specified hostcert does not exist (%s)' % hostcert)
            if not os.path.exists(certdir):
                raise ConfigurationError('Specified certdir does not exist (%s)' % certdir)

            vc[KEY] = hostkey
            vc[CERTIFICATE] = hostcert
            vc[CERTIFICATE_DIR] = certdir

        except ConfigParser.NoOptionError, e:
            # Not enough options for configuring tls context
            raise ConfigurationError('Missing TLS option: %s' % str(e))

    # backends

    backends = {}

    for section in cfg.sections():

        if ':' in section:
            backend_type, name = section.split(':',2)
        else:
            backend_type = section
            name = ''

        if name in backends:
            raise ConfigurationError('Can only have one backend named "%s"' % name)

        if backend_type in (BLOCK_DUD, BLOCK_JUNOS, BLOCK_FORCE10, BLOCK_BROCADE):
            backend_conf = dict( cfg.items(section) )
            backend_conf['_backend_type'] = backend_type
            backends[name] = backend_conf

    if not backends:
        raise ConfigurationError('No or invalid backend specified')

    vc['backend'] = backends

    return vc

