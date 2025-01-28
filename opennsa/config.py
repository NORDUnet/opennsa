"""
Configuration reader and defaults.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import os
import configparser

from opennsa import constants as cnt

# defaults
DEFAULT_CONFIG_FILE = '/etc/opennsa.conf'
DEFAULT_LOG_FILE = '/var/log/opennsa.log'
DEFAULT_TLS = 'true'
DEFAULT_TOPOLOGY_FILE = '/usr/local/share/nsi/topology.owl'
DEFAULT_TCP_PORT = 9080
DEFAULT_TLS_PORT = 9443
DEFAULT_VERIFY = True
# This will work on most mordern linux distros
DEFAULT_CERTIFICATE_DIR = '/etc/ssl/certs'

# config blocks and options
BLOCK_SERVICE = 'service'
BLOCK_DUD = 'dud'
BLOCK_JUNIPER_EX = 'juniperex'
BLOCK_JUNIPER_VPLS = 'junipervpls'
BLOCK_FORCE10 = 'force10'
BLOCK_BROCADE = 'brocade'
BLOCK_NCSVPN = 'ncsvpn'
BLOCK_PICA8OVS = 'pica8ovs'
BLOCK_JUNOSMX = 'junosmx'
BLOCK_JUNOSEX = 'junosex'
BLOCK_JUNOSSPACE = 'junosspace'
BLOCK_OESS = 'oess'
BLOCK_KYTOS = 'kytos'
BLOCK_CUSTOM_BACKEND = 'custombackend'


# service block
DOMAIN = 'domain'  # mandatory
NETWORK_NAME = 'network'  # legacy, used to be mandatory
LOG_FILE = 'logfile'
HOST = 'host'
PORT = 'port'
TLS = 'tls'
BASE_URL = 'base_url'
REST = 'rest'
NRM_MAP_FILE = 'nrmmap'
PEERS = 'peers'
POLICY = 'policy'
PLUGIN = 'plugin'
SERVICE_ID_START = 'serviceid_start'

# database
DATABASE = 'database'  # mandatory
DATABASE_USER = 'dbuser'  # mandatory
DATABASE_PASSWORD = 'dbpassword'  # can be none (os auth)
DATABASE_HOST = 'dbhost'  # can be none (local db)

# tls
KEY = 'key'  # mandatory, if tls is set
CERTIFICATE = 'certificate'  # mandatory, if tls is set
CERTIFICATE_DIR = 'certdir'  # mandatory (but dir can be empty)
VERIFY_CERT = 'verify'
ALLOWED_HOSTS = 'allowedhosts'  # comma seperated list
ALLOWED_ADMINS = 'allowed_admins'  # list of requester nsaId with administration level access

# generic stuff
_SSH_HOST = 'host'
_SSH_PORT = 'port'
_SSH_HOST_FINGERPRINT = 'fingerprint'
_SSH_USER = 'user'
_SSH_PASSWORD = 'password'
_SSH_PUBLIC_KEY = 'publickey'
_SSH_PRIVATE_KEY = 'privatekey'

AS_NUMBER = 'asnumber'

# TODO: Don't do backend specifics for everything, it causes confusion, and doesn't really solve anything

# juniper block - same for mx / ex backends
JUNIPER_HOST = _SSH_HOST
JUNIPER_PORT = _SSH_PORT
JUNIPER_HOST_FINGERPRINT = _SSH_HOST_FINGERPRINT
JUNIPER_USER = _SSH_USER
JUNIPER_SSH_PUBLIC_KEY = _SSH_PUBLIC_KEY
JUNIPER_SSH_PRIVATE_KEY = _SSH_PRIVATE_KEY

# force10 block
FORCE10_HOST = _SSH_HOST
FORCE10_PORT = _SSH_PORT
FORCE10_USER = _SSH_USER
FORCE10_PASSWORD = _SSH_PASSWORD
FORCE10_HOST_FINGERPRINT = _SSH_HOST_FINGERPRINT
FORCE10_SSH_PUBLIC_KEY = _SSH_PUBLIC_KEY
FORCE10_SSH_PRIVATE_KEY = _SSH_PRIVATE_KEY

# Brocade block
BROCADE_HOST = _SSH_HOST
BROCADE_PORT = _SSH_PORT
BROCADE_HOST_FINGERPRINT = _SSH_HOST_FINGERPRINT
BROCADE_USER = _SSH_USER
BROCADE_SSH_PUBLIC_KEY = _SSH_PUBLIC_KEY
BROCADE_SSH_PRIVATE_KEY = _SSH_PRIVATE_KEY
BROCADE_ENABLE_PASSWORD = 'enablepassword'

# Pica8 OVS
PICA8OVS_HOST = _SSH_HOST
PICA8OVS_PORT = _SSH_PORT
PICA8OVS_HOST_FINGERPRINT = _SSH_HOST_FINGERPRINT
PICA8OVS_USER = _SSH_USER
PICA8OVS_SSH_PUBLIC_KEY = _SSH_PUBLIC_KEY
PICA8OVS_SSH_PRIVATE_KEY = _SSH_PRIVATE_KEY
PICA8OVS_DB_IP = 'dbip'

# NCS VPN Backend
NCS_SERVICES_URL = 'url'
NCS_USER = 'user'
NCS_PASSWORD = 'password'

# JUNOS block
JUNOS_HOST = _SSH_HOST
JUNOS_PORT = _SSH_PORT
JUNOS_HOST_FINGERPRINT = _SSH_HOST_FINGERPRINT
JUNOS_USER = _SSH_USER
JUNOS_SSH_PUBLIC_KEY = _SSH_PUBLIC_KEY
JUNOS_SSH_PRIVATE_KEY = _SSH_PRIVATE_KEY
JUNOS_ROUTERS = 'routers'

# Junosspace backend
SPACE_USER = 'space_user'
SPACE_PASSWORD = 'space_password'
SPACE_API_URL = 'space_api_url'
SPACE_ROUTERS = 'routers'
SPACE_CONFIGLET_ACTIVATE_LOCAL = 'configlet_activate_local'
SPACE_CONFIGLET_ACTIVATE_REMOTE = 'configlet_activate_remote'
SPACE_CONFIGLET_DEACTIVATE_LOCAL = 'configlet_deactivate_local'
SPACE_CONFIGLET_DEACTIVATE_REMOTE = 'configlet_deactivate_remote'

# OESS
OESS_URL = 'url'
OESS_USER = 'username'
OESS_PASSWORD = 'password'
OESS_WORKGROUP = 'workgroup'

# Kytos
KYTOS_URL = 'url'
KYTOS_USER = 'username'
KYTOS_PASSWORD = 'password'


class ConfigurationError(Exception):
    """
    Raised in case of invalid/inconsistent configuration.
    """


class Peer(object):

    def __init__(self, url, cost):
        self.url = url
        self.cost = cost


class EnvInterpolation(configparser.BasicInterpolation):
    """Interpolation which expands environment variables in values."""

    def before_get(self, parser, section, option, value, defaults):
        value = super().before_get(parser, section, option, value, defaults)
        return os.path.expandvars(value)


class Config(object):
    """
    Singleton instance of configuration class.  Loads the config and persists it to class object.

    Also, provides utility function around the loaded configuration
    """
    _instance = None

    def __init__(self):
        raise RuntimeError("Call instance() instead, singleton class")

    @classmethod
    def instance(cls):
        if cls._instance is None:
            print('Creating new instance')
            cls._instance = cls.__new__(cls)
            cls._instance.cfg = None
            cls._instance.vc = None
            # Put any initialization here.
        return cls._instance

    def read_config(self, filename):
        """
        Load the configuration from a given file
        """
        if self._instance.cfg is None:
            cfg = configparser.ConfigParser(interpolation=EnvInterpolation())
            cfg.add_section(BLOCK_SERVICE)
            cfg.read([filename])
            self._instance.cfg = cfg
        return self._instance.cfg, self._read_verify_config()

    def _read_verify_config(self):
        """
        Returns a dictionary of the loaded config once verified
        """
        if self._instance.vc is None:
            self._instance.vc = self._load_config_dict()
        return self._instance.vc

    def config_dict(self):
        """
        Returns the loaded dict if one exists, or an empty one otherwise.
        """
        return self._instance.vc if self._instance.vc is not None else {}

    @property
    def allowed_admins(self):
        """
        Property returns array of allowed admins
        """
        return self.config_dict().get(ALLOWED_ADMINS, '')

    def is_admin_override(self, urn):
        """
        Check if the URN matches a valid admin.  Allowing all queries to execute
        """
        admins = self.allowed_admins
        for entry in self.allowed_admins:
            if entry == urn:
                return True
        return False

    def _load_database_config(self, vc):
        # vc = self._instance.vc
        cfg = self._instance.cfg
        # database
        try:
            vc[DATABASE] = cfg.get(BLOCK_SERVICE, DATABASE)
        except configparser.NoOptionError:
            raise ConfigurationError(
                'No database specified in configuration file (mandatory)')

        try:
            vc[DATABASE_USER] = cfg.get(BLOCK_SERVICE, DATABASE_USER)
        except configparser.NoOptionError:
            raise ConfigurationError(
                'No database user specified in configuration file (mandatory)')

        vc[DATABASE_PASSWORD] = cfg.get(BLOCK_SERVICE, DATABASE_PASSWORD, fallback=None)
        vc[DATABASE_HOST] = cfg.get(BLOCK_SERVICE, DATABASE_HOST, fallback='localhost')
        vc[SERVICE_ID_START] = cfg.get(BLOCK_SERVICE, SERVICE_ID_START, fallback=None)

    def _load_config_dict(self) -> dict:
        """
        Read a config and verify that things are correct. Will also fill in
        default values where applicable.

        This is supposed to be used during application creation (before service
        start) to ensure that simple configuration errors do not pop up efter
        daemonization.

        Returns a "verified" config, which is a dictionary.
        """
        cfg = self._instance.cfg
        vc = {}

        # Check for deprecated / old invalid stuff

        try:
            cfg.get(BLOCK_SERVICE, NRM_MAP_FILE)
            raise ConfigurationError(
                'NRM Map file should be specified under backend')
        except configparser.NoOptionError:
            pass

        # check / extract

        try:
            vc[DOMAIN] = cfg.get(BLOCK_SERVICE, DOMAIN)
        except configparser.NoOptionError:
            raise ConfigurationError(
                'No domain name specified in configuration file (mandatory, see docs/migration)')

        try:
            cfg.get(BLOCK_SERVICE, NETWORK_NAME)
            raise ConfigurationError(
                'Network name no longer used, use domain (see docs/migration)')
        except configparser.NoOptionError:
            pass

        vc[LOG_FILE] = cfg.get(BLOCK_SERVICE, LOG_FILE, fallback=DEFAULT_LOG_FILE)

        try:
            nrm_map_file = cfg.get(BLOCK_SERVICE, NRM_MAP_FILE)
            if not os.path.exists(nrm_map_file):
                raise ConfigurationError(
                    'Specified NRM mapping file does not exist (%s)' % nrm_map_file)
            vc[NRM_MAP_FILE] = nrm_map_file
        except configparser.NoOptionError:
            vc[NRM_MAP_FILE] = None

        vc[REST] = cfg.getboolean(BLOCK_SERVICE, REST, fallback=False)

        try:
            peers_raw = cfg.get(BLOCK_SERVICE, PEERS)
            vc[PEERS] = [Peer(purl.strip(), 1) for purl in peers_raw.split('\n')]
        except configparser.NoOptionError:
            vc[PEERS] = None

        vc[HOST] = cfg.get(BLOCK_SERVICE, HOST, fallback=None)
        vc[TLS] = cfg.getboolean(BLOCK_SERVICE, TLS, fallback=DEFAULT_TLS)
        vc[PORT] = cfg.getint(BLOCK_SERVICE, PORT, fallback=DEFAULT_TLS_PORT if vc[TLS] else DEFAULT_TCP_PORT)

        try:
            vc[BASE_URL] = cfg.get(BLOCK_SERVICE, BASE_URL)
        except configparser.NoOptionError:
            vc[BASE_URL] = None

        try:
            vc[KEY] = cfg.get(BLOCK_SERVICE, KEY)
        except configparser.NoOptionError:
            vc[KEY] = None

        try:
            vc[CERTIFICATE] = cfg.get(BLOCK_SERVICE, CERTIFICATE)
        except configparser.NoOptionError:
            vc[CERTIFICATE] = None

        try:
            policies = cfg.get(BLOCK_SERVICE, POLICY).split(',')
            for policy in policies:
                if not policy in (cnt.REQUIRE_USER, cnt.REQUIRE_TRACE, cnt.AGGREGATOR, cnt.ALLOW_HAIRPIN):
                    raise ConfigurationError('Invalid policy: %s' % policy)
            vc[POLICY] = policies
        except configparser.NoOptionError:
            vc[POLICY] = []

        vc[PLUGIN] = cfg.get(BLOCK_SERVICE, PLUGIN, fallback=None)

        self._load_database_config(vc)
        self._load_certificates(vc)

        ## Set override of allowed Admins
        allowed_hosts_admins = cfg.get(BLOCK_SERVICE, ALLOWED_ADMINS, fallback='')
        vc[ALLOWED_ADMINS] = [i.strip() for i in allowed_hosts_admins.split(',') if len(i) > 0]

        # backends
        self._load_backends(vc)
        return vc

    def _load_certificates(self, vc):
        cfg = self._instance.cfg
        # we always extract certdir and verify as we need that for performing https requests
        try:
            certdir = cfg.get(BLOCK_SERVICE, CERTIFICATE_DIR)
            if not os.path.exists(certdir):
                raise ConfigurationError(
                    'Specified certdir does not exist (%s)' % certdir)
            vc[CERTIFICATE_DIR] = certdir
        except configparser.NoOptionError:
            vc[CERTIFICATE_DIR] = DEFAULT_CERTIFICATE_DIR
        try:
            vc[VERIFY_CERT] = cfg.getboolean(BLOCK_SERVICE, VERIFY_CERT)
        except configparser.NoOptionError:
            vc[VERIFY_CERT] = DEFAULT_VERIFY

        # tls
        if vc[TLS]:
            try:
                if not vc[KEY]:
                    raise ConfigurationError(
                        'must specify a key when TLS is enabled')
                elif not os.path.exists(vc[KEY]):
                    raise ConfigurationError(
                        'Specified key does not exist (%s)' % vc[KEY])

                if not vc[CERTIFICATE]:
                    raise ConfigurationError(
                        'must specify a certificate when TLS is enabled')
                elif not os.path.exists(vc[CERTIFICATE]):
                    raise ConfigurationError(
                        'Specified certificate does not exist (%s)' % vc[CERTIFICATE])

                try:
                    allowed_hosts_cfg = cfg.get(BLOCK_SERVICE, ALLOWED_HOSTS)
                    vc[ALLOWED_HOSTS] = [i.strip() for i in allowed_hosts_cfg.split(',') if len(i) > 0]

                except:
                    pass

            except configparser.NoOptionError as e:
                # Not enough options for configuring tls context
                raise ConfigurationError('Missing TLS option: %s' % str(e))

    def _load_backends(self, vc):
        """
        Verify and load backends into configuration class
        """
        cfg = self._instance.cfg
        backends = {}

        for section in cfg.sections():

            if section == 'service':
                continue

            if ':' in section:
                backend_type, name = section.split(':', 2)
            else:
                backend_type = section
                name = ''

            if name in backends:
                raise ConfigurationError(
                    'Can only have one backend named "%s"' % name)

            if backend_type in (
                    BLOCK_DUD, BLOCK_JUNIPER_EX, BLOCK_JUNIPER_VPLS, BLOCK_JUNOSMX, BLOCK_FORCE10, BLOCK_BROCADE,
                    BLOCK_NCSVPN, BLOCK_PICA8OVS, BLOCK_OESS, BLOCK_KYTOS, BLOCK_JUNOSSPACE, BLOCK_JUNOSEX,
                    BLOCK_CUSTOM_BACKEND, 'asyncfail'):
                backend_conf = dict(cfg.items(section))
                backend_conf['_backend_type'] = backend_type
                backends[name] = backend_conf

        vc['backend'] = backends
