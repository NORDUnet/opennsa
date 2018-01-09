"""
Configuration reader and defaults.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import os
import ConfigParser

from opennsa import constants as cnt



# defaults
DEFAULT_CONFIG_FILE     = '/etc/opennsa.conf'
DEFAULT_LOG_FILE        = '/var/log/opennsa.log'
DEFAULT_TLS             = 'true'
DEFAULT_TOPOLOGY_FILE   = '/usr/local/share/nsi/topology.owl'
DEFAULT_TCP_PORT        = 9080
DEFAULT_TLS_PORT        = 9443
DEFAULT_VERIFY          = True
DEFAULT_CERTIFICATE_DIR = '/etc/ssl/certs' # This will work on most mordern linux distros


# config blocks and options
BLOCK_SERVICE    = 'service'
BLOCK_DUD        = 'dud'
BLOCK_JUNIPER_EX = 'juniperex'
BLOCK_JUNIPER_VPLS = 'junipervpls'
BLOCK_FORCE10    = 'force10'
BLOCK_BROCADE    = 'brocade'
BLOCK_NCSVPN     = 'ncsvpn'
BLOCK_PICA8OVS   = 'pica8ovs'
BLOCK_JUNOSMX    = 'junosmx'
BLOCK_JUNOSEX    = 'junosex'
BLOCK_JUNOSSPACE = 'junosspace'
BLOCK_OESS       = 'oess'
BLOCK_CUSTOM_BACKEND = 'custombackend'

# service block
NETWORK_NAME     = 'network'     # mandatory
LOG_FILE         = 'logfile'
HOST             = 'host'
PORT             = 'port'
TLS              = 'tls'
REST             = 'rest'
NRM_MAP_FILE     = 'nrmmap'
PEERS            = 'peers'
POLICY           = 'policy'
PLUGIN           = 'plugin'
SERVICE_ID_START = 'serviceid_start'

# database
DATABASE                = 'database'    # mandatory
DATABASE_USER           = 'dbuser'      # mandatory
DATABASE_PASSWORD       = 'dbpassword'  # can be none (os auth)
DATABASE_HOST           = 'dbhost'      # can be none (local db)

# tls
KEY                     = 'key'         # mandatory, if tls is set
CERTIFICATE             = 'certificate' # mandatory, if tls is set
CERTIFICATE_DIR         = 'certdir'     # mandatory (but dir can be empty)
VERIFY_CERT             = 'verify'
ALLOWED_HOSTS           = 'allowedhosts' # comma seperated list

# generic stuff
_SSH_HOST               = 'host'
_SSH_PORT               = 'port'
_SSH_HOST_FINGERPRINT   = 'fingerprint'
_SSH_USER               = 'user'
_SSH_PASSWORD           = 'password'
_SSH_PUBLIC_KEY         = 'publickey'
_SSH_PRIVATE_KEY        = 'privatekey'

AS_NUMBER              = 'asnumber'

# TODO: Don't do backend specifics for everything, it causes confusion, and doesn't really solve anything

# juniper block - same for mx / ex backends
JUNIPER_HOST                = _SSH_HOST
JUNIPER_PORT                = _SSH_PORT
JUNIPER_HOST_FINGERPRINT    = _SSH_HOST_FINGERPRINT
JUNIPER_USER                = _SSH_USER
JUNIPER_SSH_PUBLIC_KEY      = _SSH_PUBLIC_KEY
JUNIPER_SSH_PRIVATE_KEY     = _SSH_PRIVATE_KEY

# force10 block
FORCE10_HOST            = _SSH_HOST
FORCE10_PORT            = _SSH_PORT
FORCE10_USER            = _SSH_USER
FORCE10_PASSWORD        = _SSH_PASSWORD
FORCE10_HOST_FINGERPRINT = _SSH_HOST_FINGERPRINT
FORCE10_SSH_PUBLIC_KEY  = _SSH_PUBLIC_KEY
FORCE10_SSH_PRIVATE_KEY = _SSH_PRIVATE_KEY

# Brocade block
BROCADE_HOST              = _SSH_HOST
BROCADE_PORT              = _SSH_PORT
BROCADE_HOST_FINGERPRINT  = _SSH_HOST_FINGERPRINT
BROCADE_USER              = _SSH_USER
BROCADE_SSH_PUBLIC_KEY    = _SSH_PUBLIC_KEY
BROCADE_SSH_PRIVATE_KEY   = _SSH_PRIVATE_KEY
BROCADE_ENABLE_PASSWORD   = 'enablepassword'

# Pica8 OVS
PICA8OVS_HOST                = _SSH_HOST
PICA8OVS_PORT                = _SSH_PORT
PICA8OVS_HOST_FINGERPRINT    = _SSH_HOST_FINGERPRINT
PICA8OVS_USER                = _SSH_USER
PICA8OVS_SSH_PUBLIC_KEY      = _SSH_PUBLIC_KEY
PICA8OVS_SSH_PRIVATE_KEY     = _SSH_PRIVATE_KEY
PICA8OVS_DB_IP               = 'dbip'


# NCS VPN Backend
NCS_SERVICES_URL        = 'url'
NCS_USER                = 'user'
NCS_PASSWORD            = 'password'

# JUNOS block
JUNOS_HOST                = _SSH_HOST
JUNOS_PORT                = _SSH_PORT
JUNOS_HOST_FINGERPRINT    = _SSH_HOST_FINGERPRINT
JUNOS_USER                = _SSH_USER
JUNOS_SSH_PUBLIC_KEY      = _SSH_PUBLIC_KEY
JUNOS_SSH_PRIVATE_KEY     = _SSH_PRIVATE_KEY
JUNOS_ROUTERS             = 'routers'

#Junosspace backend
SPACE_USER              = 'space_user'
SPACE_PASSWORD          = 'space_password'
SPACE_API_URL           = 'space_api_url'
SPACE_ROUTERS           = 'routers'
SPACE_CONFIGLET_ACTIVATE_LOCAL = 'configlet_activate_local'  
SPACE_CONFIGLET_ACTIVATE_REMOTE = 'configlet_activate_remote'
SPACE_CONFIGLET_DEACTIVATE_LOCAL = 'configlet_deactivate_local'
SPACE_CONFIGLET_DEACTIVATE_REMOTE = 'configlet_deactivate_remote'

# OESS
OESS_URL                = 'url'
OESS_USER               = 'username'
OESS_PASSWORD           = 'password'
OESS_WORKGROUP          = 'workgroup'


class ConfigurationError(Exception):
    """
    Raised in case of invalid/inconsistent configuration.
    """


class Peer(object):

    def __init__(self, url, cost):
        self.url = url
        self.cost = cost



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
        nrm_map_file = cfg.get(BLOCK_SERVICE, NRM_MAP_FILE)
        if not os.path.exists(nrm_map_file):
            raise ConfigurationError('Specified NRM mapping file does not exist (%s)' % nrm_map_file)
        vc[NRM_MAP_FILE] = nrm_map_file
    except ConfigParser.NoOptionError:
        vc[NRM_MAP_FILE] = None

    try:
        vc[REST] = cfg.getboolean(BLOCK_SERVICE, REST)
    except ConfigParser.NoOptionError:
        vc[REST] = False

    try:
        peers_raw = cfg.get(BLOCK_SERVICE, PEERS)
        vc[PEERS] = [ Peer(purl, 1) for purl in  peers_raw.split('\n') ]
    except ConfigParser.NoOptionError:
        vc[PEERS] = None

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

    try:
        policies = cfg.get(BLOCK_SERVICE, POLICY).split(',')
        for policy in policies:
            if not policy in (cnt.REQUIRE_USER, cnt.REQUIRE_TRACE, cnt.AGGREGATOR, cnt.ALLOW_HAIRPIN):
                raise ConfigurationError('Invalid policy: %s' % policy)
        vc[POLICY] = policies
    except ConfigParser.NoOptionError:
        vc[POLICY] = []

    try:
        vc[PLUGIN] = cfg.get(BLOCK_SERVICE, PLUGIN)
    except ConfigParser.NoOptionError:
        vc[PLUGIN] = None

    # database
    try:
        vc[DATABASE] = cfg.get(BLOCK_SERVICE, DATABASE)
    except ConfigParser.NoOptionError:
        raise ConfigurationError('No database specified in configuration file (mandatory)')

    try:
        vc[DATABASE_USER] = cfg.get(BLOCK_SERVICE, DATABASE_USER)
    except ConfigParser.NoOptionError:
        raise ConfigurationError('No database user specified in configuration file (mandatory)')

    try:
        vc[DATABASE_PASSWORD] = cfg.get(BLOCK_SERVICE, DATABASE_PASSWORD)
    except ConfigParser.NoOptionError:
        vc[DATABASE_PASSWORD] = None

    try:
        vc[DATABASE_HOST] = cfg.get(BLOCK_SERVICE, DATABASE_HOST)
    except ConfigParser.NoOptionError:
        vc[DATABASE_HOST] = None

    try:
        vc[SERVICE_ID_START] = cfg.get(BLOCK_SERVICE, SERVICE_ID_START)
    except ConfigParser.NoOptionError:
        vc[SERVICE_ID_START] = None

    # we always extract certdir and verify as we need that for performing https requests
    try:
        certdir = cfg.get(BLOCK_SERVICE, CERTIFICATE_DIR)
        if not os.path.exists(certdir):
            raise ConfigurationError('Specified certdir does not exist (%s)' % certdir)
        vc[CERTIFICATE_DIR] = certdir
    except ConfigParser.NoOptionError, e:
        vc[CERTIFICATE_DIR] = DEFAULT_CERTIFICATE_DIR
    try:
        vc[VERIFY_CERT] = cfg.getboolean(BLOCK_SERVICE, VERIFY_CERT)
    except ConfigParser.NoOptionError:
        vc[VERIFY_CERT] = DEFAULT_VERIFY

    # tls
    if vc[TLS]:
        try:
            hostkey  = cfg.get(BLOCK_SERVICE, KEY)
            hostcert = cfg.get(BLOCK_SERVICE, CERTIFICATE)

            if not os.path.exists(hostkey):
                raise ConfigurationError('Specified hostkey does not exist (%s)' % hostkey)
            if not os.path.exists(hostcert):
                raise ConfigurationError('Specified hostcert does not exist (%s)' % hostcert)

            vc[KEY] = hostkey
            vc[CERTIFICATE] = hostcert

            try:
                allowed_hosts_cfg = cfg.get(BLOCK_SERVICE, ALLOWED_HOSTS)
                vc[ALLOWED_HOSTS] = allowed_hosts_cfg.split(',')
            except:
                pass

        except ConfigParser.NoOptionError, e:
            # Not enough options for configuring tls context
            raise ConfigurationError('Missing TLS option: %s' % str(e))


    # backends
    backends = {}

    for section in cfg.sections():

        if section == 'service':
            continue

        if ':' in section:
            backend_type, name = section.split(':',2)
        else:
            backend_type = section
            name = ''

        if name in backends:
            raise ConfigurationError('Can only have one backend named "%s"' % name)

        if backend_type in (BLOCK_DUD, BLOCK_JUNIPER_EX, BLOCK_JUNIPER_VPLS, BLOCK_JUNOSMX, BLOCK_FORCE10, BLOCK_BROCADE,
                            BLOCK_NCSVPN, BLOCK_PICA8OVS, BLOCK_OESS, BLOCK_JUNOSSPACE, BLOCK_JUNOSEX,
                            BLOCK_CUSTOM_BACKEND, 'asyncfail'):
            backend_conf = dict( cfg.items(section) )
            backend_conf['_backend_type'] = backend_type
            backends[name] = backend_conf

    vc['backend'] = backends

    return vc
