"""
High-level functionality for creating clients and services in OpenNSA.
"""

import os
from ConfigParser import NoOptionError

from twisted.python.log import ILogObserver
from twisted.application import internet, service as appservice

from opennsa import config, logging, registry, topology, nsiservice
from opennsa.protocols.webservice import client, service, provider, requester, resource



class ConfigurationError(Exception):
    """
    Raised in case of invalid/inconsistent configuration.
    """


def _createServiceURL(host, port, ctx_factory=None):

    if ctx_factory:
        proto_scheme = 'https://'
    else:
        proto_scheme = 'http://'

    service_url = proto_scheme + '%s:%i/NSI/services/ConnectionService' % (host,port)
    return service_url



def createService(network_name, topology_sources, backend, service_registry, host, port, wsdl_dir, ctx_factory=None, nrm_map_source=None):


    # reminds an awful lot about client setup

    service_url = _createServiceURL(host, port, ctx_factory)
    nsi_resource, site = resource.createService()

    provider_client     = client.ProviderClient(service_url, wsdl_dir, ctx_factory=ctx_factory)
    nsi_requester = requester.Requester(provider_client, 30)
    service.RequesterService(nsi_resource, nsi_requester, wsdl_dir)

    # now provider service

    topo = topology.parseTopology(topology_sources, nrm_map_source)
    nsi_service  = nsiservice.NSIService(network_name, backend, service_registry, topo, nsi_requester)

    requester_client = client.RequesterClient(wsdl_dir, ctx_factory)
    nsi_provider = provider.Provider(service_registry, requester_client)
    service.ProviderService(nsi_resource, nsi_provider, wsdl_dir)

    return site



def createClient(host, port, wsdl_dir, ctx_factory=None):

    service_url = _createServiceURL(host, port, ctx_factory)
    nsi_resource, site = resource.createService()

    provider_client     = client.ProviderClient(service_url, wsdl_dir, ctx_factory=ctx_factory)
    nsi_requester = requester.Requester(provider_client, callback_timeout=65)
    service.RequesterService(nsi_resource, nsi_requester, wsdl_dir)

    return nsi_requester, site



def createApplication(config_file=config.DEFAULT_CONFIG_FILE, authz_verify=True, debug=False):

    cfg = config.readConfig(config_file)

    try:
        network_name = cfg.get(config.BLOCK_SERVICE, config.CONFIG_NETWORK_NAME)
    except NoOptionError:
        raise ConfigurationError('No network name specified in configuration file (mandatory)')

    log_file_path = cfg.get(config.BLOCK_SERVICE, config.CONFIG_LOG_FILE)
    if log_file_path:
        log_file = open(log_file_path, 'a')
    else:
        import sys
        log_file = sys.stdout

    topology_list = cfg.get(config.BLOCK_SERVICE, config.CONFIG_TOPOLOGY_FILE)
    topology_files = topology_list.split(',')
    for topology_file in topology_files:
        if not os.path.exists(topology_file):
            raise ConfigurationError('Specified (or default) topology file does not exist (%s)' % topology_file)
    topology_sources = [ open(tf) for tf in topology_files ]

    try:
        nrm_map_file = cfg.get(config.BLOCK_SERVICE, config.CONFIG_NRM_MAP_FILE)
        if not os.path.exists(nrm_map_file):
            raise ConfigurationError('Specified NRM mapping file does not exist (%s)' % nrm_map_file)
        nrm_map_source = open(nrm_map_file)
    except NoOptionError:
        nrm_map_source = None


    wsdl_dir = cfg.get(config.BLOCK_SERVICE, config.CONFIG_WSDL_DIRECTORY)
    if not os.path.exists(wsdl_dir):
        raise ConfigurationError('Specified (or default) WSDL directory does not exist (%s)' % wsdl_dir)

    try:
        host = cfg.get(config.BLOCK_SERVICE, config.CONFIG_HOST)
    except NoOptionError:
        import socket
        host = socket.getfqdn() # this a guess

    try:
        tls = cfg.getboolean(config.BLOCK_SERVICE, config.CONFIG_TLS)
    except NoOptionError:
        tls = config.DEFAULT_TLS

    try:
        port = cfg.getint(config.BLOCK_SERVICE, config.CONFIG_PORT)
    except NoOptionError:
        port = config.DEFAULT_TLS_PORT if tls else config.DEFAULT_TCP_PORT

    ctx_factory = None
    try:
        hostkey  = cfg.get(config.BLOCK_SERVICE, config.CONFIG_HOSTKEY)
        hostcert = cfg.get(config.BLOCK_SERVICE, config.CONFIG_HOSTCERT)
        certdir  = cfg.get(config.BLOCK_SERVICE, config.CONFIG_CERTIFICATE_DIR)
        try:
            verify = cfg.get(config.BLOCK_SERVICE, config.CONFIG_VERIFY)
        except NoOptionError, e:
            verify = config.DEFAULT_VERIFY

        if not os.path.exists(hostkey):
            raise ConfigurationError('Specified hostkey does not exists (%s)' % hostkey)
        if not os.path.exists(hostcert):
            raise ConfigurationError('Specified hostcert does not exists (%s)' % hostcert)
        if not os.path.exists(certdir):
            raise ConfigurationError('Specified certdir does not exists (%s)' % certdir)

        from opennsa import ctxfactory
        ctx_factory = ctxfactory.ContextFactory(hostkey, hostcert, certdir, verify)
    except NoOptionError, e:
        # Not enough options for configuring tls context
        if tls:
            raise ConfigurationError('Missing TLS option: %s' % str(e))

    # backend

    if config.BLOCK_DUD in cfg.sections():
        from opennsa.backends import dud
        backend = dud.DUDNSIBackend(network_name)
    elif config.BLOCK_JUNOS in cfg.sections():
        from opennsa.backends import junos
        backend = junos.JunOSBackend(network_name, cfg.items(config.BLOCK_JUNOS))
    elif config.BLOCK_FORCE10 in cfg.sections():
        from opennsa.backends import force10
        backend = force10.Force10Backend(network_name, cfg.items(config.BLOCK_FORCE10))
    elif config.BLOCK_ARGIA in cfg.sections():
        from opennsa.backends import argia
        backend = argia.ArgiaBackend(network_name, cfg.items(config.BLOCK_ARGIA))
    else:
        raise ConfigurationError('No or invalid backend specified')

    # setup application


    service_registry = registry.ServiceRegistry()

    factory = createService(network_name, topology_sources, backend, service_registry, host, port, wsdl_dir, ctx_factory, nrm_map_source)

    application = appservice.Application("OpenNSA")
    application.setComponent(ILogObserver, logging.DebugLogObserver(log_file, debug).emit)

    if tls:
        internet.SSLServer(port, factory, ctx_factory).setServiceParent(application)
    else:
        internet.TCPServer(port, factory).setServiceParent(application)

    return application

