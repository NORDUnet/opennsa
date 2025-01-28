"""
High-level functionality for creating clients and services in OpenNSA.

Binds all the OpenNSA modules together into a useful service.
This is a tad complex.

Beware that the Twisted HTTP module should be fed paths in bytes, not string,
or nothing will work.

TODO:
Split out the main setup into some more comprehensible parts.
Split out the main setup so the site can be retrieved without the service (so the whole thing can be tested).

"""

import os
import hashlib
import datetime
import importlib

from twisted.python import log
from twisted.web import resource, server
from twisted.application import internet, service as twistedservice

from opennsa import __version__ as version

from opennsa.config import Config
from opennsa import config, logging, constants as cnt, nsa, provreg, database, aggregator, viewresource
from opennsa.topology import nrm, nml, linkvector, service as nmlservice
from opennsa.protocols import rest, nsi2
from opennsa.protocols.shared import httplog
from opennsa.discovery import service as discoveryservice, fetcher

NSI_RESOURCE = b'NSI'


def setupBackend(backend_cfg, network_name, nrm_ports, parent_requester):
    bc = backend_cfg.copy()
    backend_type = backend_cfg.pop('_backend_type')

    if backend_type == config.BLOCK_DUD:
        from opennsa.backends import dud
        BackendConstructer = dud.DUDNSIBackend

    elif backend_type == config.BLOCK_JUNOSMX:
        from opennsa.backends import junosmx
        BackendConstructer = junosmx.JUNOSMXBackend

    elif backend_type == config.BLOCK_FORCE10:
        from opennsa.backends import force10
        BackendConstructer = force10.Force10Backend

    elif backend_type == config.BLOCK_JUNIPER_EX:
        from opennsa.backends import juniperex
        BackendConstructer = juniperex.JuniperEXBackend

    elif backend_type == config.BLOCK_JUNIPER_VPLS:
        from opennsa.backends import junipervpls
        BackendConstructer = junipervpls.JuniperVPLSBackend

    elif backend_type == config.BLOCK_BROCADE:
        from opennsa.backends import brocade
        BackendConstructer = brocade.BrocadeBackend

    elif backend_type == config.BLOCK_NCSVPN:
        from opennsa.backends import ncsvpn
        BackendConstructer = ncsvpn.NCSVPNBackend

    elif backend_type == config.BLOCK_PICA8OVS:
        from opennsa.backends import pica8ovs
        BackendConstructer = pica8ovs.Pica8OVSBackend

    elif backend_type == config.BLOCK_JUNOSSPACE:
        from opennsa.backends import junosspace
        BackendConstructer = junosspace.JUNOSSPACEBackend

    elif backend_type == config.BLOCK_JUNOSEX:
        from opennsa.backends import junosex
        BackendConstructer = junosex.JunosEXBackend

    elif backend_type == config.BLOCK_OESS:
        from opennsa.backends import oess
        BackendConstructer = oess.OESSBackend

    elif backend_type == config.BLOCK_KYTOS:
        from opennsa.backends import kytos
        BackendConstructer = kytos.KytosBackend

    elif backend_type == config.BLOCK_CUSTOM_BACKEND:
        module_name = backend_cfg.pop('module')
        try:
            module = importlib.import_module(module_name)
            BackendConstructer = module.Backend
        except Exception as e:
            log.msg('Failed to load backend {}:\n{}'.format(module_name, e))
            raise config.ConfigurationError('Failed to load backend')
    else:
        raise config.ConfigurationError('No backend specified')

    b = BackendConstructer(network_name, nrm_ports, parent_requester, bc)
    return b


def setupTLSContext(vc):
    # ssl/tls contxt
    if vc[config.KEY] and vc[config.CERTIFICATE]:
        log.msg('setup full 2Way TLS context')
        from opennsa.opennsaTlsContext import opennsa2WayTlsContext
        ctx_factory = opennsa2WayTlsContext(
            vc[config.KEY], vc[config.CERTIFICATE], vc[config.CERTIFICATE_DIR], vc[config.VERIFY_CERT])
    else:
        from opennsa.opennsaTlsContext import opennsaTlsContext
        log.msg('setup client TLS context without client authentication')
        ctx_factory = opennsaTlsContext(
            vc[config.CERTIFICATE_DIR], vc[config.VERIFY_CERT])

    return ctx_factory


class CS2RequesterCreator:

    def __init__(self, top_resource, aggregator, host, port, tls, ctx_factory):
        self.top_resource = top_resource
        self.aggregator = aggregator
        self.host = host
        self.port = port
        self.tls = tls
        self.ctx_factory = ctx_factory

    def create(self, nsi_agent):
        hash_input = nsi_agent.urn() + nsi_agent.endpoint
        resource_name = b'RequesterService2-' + \
                        hashlib.sha1(hash_input.encode()).hexdigest().encode()
        return nsi2.setupRequesterPair(self.top_resource, self.host, self.port, nsi_agent.endpoint, self.aggregator,
                                       resource_name, tls=self.tls, ctx_factory=self.ctx_factory)


class OpenNSAService(twistedservice.MultiService):

    def __init__(self, vc):
        twistedservice.MultiService.__init__(self)
        self.vc = vc

    def setupServiceFactory(self):
        """
        This sets up the OpenNSA service and ties together everything in the initialization.
        There are a lot of things going on, but none of it it particular deep.
        """
        log.msg('OpenNSA service initializing')

        vc = self.vc

        now = datetime.datetime.utcnow().replace(microsecond=0)

        if vc[config.HOST] is None:
            # guess name if not configured
            import socket
            vc[config.HOST] = socket.getfqdn()

        # database
        database.setupDatabase(vc[config.DATABASE], vc[config.DATABASE_USER],
                               vc[config.DATABASE_PASSWORD], vc[config.DATABASE_HOST], vc[config.SERVICE_ID_START])

        service_endpoints = []

        # base names
        domain_name = vc[config.DOMAIN]  # FIXME rename variable to domain
        nsa_name = domain_name + ':nsa'

        # base url
        if vc[config.BASE_URL]:
            base_url = vc[config.BASE_URL]
        else:
            base_protocol = 'https://' if vc[config.TLS] else 'http://'
            base_url = base_protocol + vc[config.HOST] + ':' + str(vc[config.PORT])

        # nsi endpoint and agent
        provider_endpoint = base_url + '/NSI/services/CS2'  # hardcode for now
        service_endpoints.append(('Provider', provider_endpoint))

        ns_agent = nsa.NetworkServiceAgent(
            nsa_name, provider_endpoint, 'local')

        # ssl/tls context
        ctx_factory = setupTLSContext(vc)  # May be None

        # plugin
        if vc[config.PLUGIN]:
            from twisted.python import reflect
            plugin = reflect.namedAny(
                'opennsa.plugins.%s.plugin' % vc[config.PLUGIN])
        else:
            from opennsa.plugin import BasePlugin
            plugin = BasePlugin()

        plugin.init(vc, ctx_factory)

        # the dance to setup dynamic providers right
        top_resource = resource.Resource()
        requester_creator = CS2RequesterCreator(
            top_resource, None, vc[config.HOST], vc[config.PORT], vc[config.TLS], ctx_factory)  # set aggregator later

        provider_registry = provreg.ProviderRegistry(
            {cnt.CS2_SERVICE_TYPE: requester_creator.create})

        link_vector = linkvector.LinkVector()

        networks = {}
        ports = {}  # { network : { port : nrmport } }

        parent_requester = None  # parent requester is set later
        aggr = aggregator.Aggregator(
            ns_agent, ports, link_vector, parent_requester, provider_registry, vc[config.POLICY], plugin)

        requester_creator.aggregator = aggr

        pc = nsi2.setupProvider(
            aggr, top_resource, ctx_factory=ctx_factory, allowed_hosts=vc.get(config.ALLOWED_HOSTS))
        aggr.parent_requester = pc

        # setup backend(s) - for now we only support one
        backend_configs = vc['backend']
        if len(backend_configs) == 0:
            log.msg('No backend specified. Running in aggregator-only mode')
            if not cnt.AGGREGATOR in vc[config.POLICY]:
                vc[config.POLICY].append(cnt.AGGREGATOR)

        else:  # at least one backend

            # This is all temporary right now... clean up later

            for backend_name, b_cfg in backend_configs.items():

                if backend_name is None or backend_name == '':
                    raise config.ConfigurationError(
                        'You need to specify backend name, use [backend:name]')

                backend_network_name = '{}:{}'.format(
                    domain_name, backend_name)

                if not config.NRM_MAP_FILE in b_cfg:  # move to verify config
                    raise config.ConfigurationError(
                        'No nrm map specified for backend')

                backend_nrm_map_file = b_cfg[config.NRM_MAP_FILE]
                if not os.path.exists(backend_nrm_map_file):  # move to verify config
                    raise config.ConfigError('nrm map file {} for backend {} does not exists'.format(
                        backend_nrm_map_file, backend_name))

                nrm_map = open(backend_nrm_map_file)
                backend_nrm_ports = nrm.parsePortSpec(nrm_map)

                link_vector.addLocalNetwork(backend_network_name)
                for np in backend_nrm_ports:
                    if np.remote_network is not None:
                        link_vector.updateVector(backend_network_name, np.name, {
                            np.remote_network: 1})  # hack
                        for network, cost in np.vectors.items():
                            link_vector.updateVector(np.name, {network: cost})
                    # build port map for aggreator to lookup
                    ports.setdefault(backend_network_name, {})[np.name] = np

                backend_service = setupBackend(
                    b_cfg, backend_network_name, backend_nrm_ports, aggr)

                networks[backend_network_name] = {
                    'backend': backend_service,
                    'nrm_ports': backend_nrm_ports
                }

                provider_registry.addProvider(
                    ns_agent.urn(), backend_network_name, backend_service)

        # fetcher
        if vc[config.PEERS]:
            fetcher_service = fetcher.FetcherService(
                link_vector, networks, vc[config.PEERS], provider_registry, ctx_factory=ctx_factory)
            fetcher_service.setServiceParent(self)
        else:
            log.msg(
                'No peers configured, will not be able to do outbound requests (UPA mode)')

        # discovery service
        opennsa_version = 'OpenNSA-' + version
        network_urns = ['{}{}'.format(
            cnt.URN_OGF_PREFIX, network_name) for network_name in networks]
        interfaces = [(cnt.CS2_PROVIDER, provider_endpoint, None),
                      (cnt.CS2_SERVICE_TYPE, provider_endpoint, None)]
        features = []
        if networks:
            features.append((cnt.FEATURE_UPA, None))
        if vc[config.PEERS]:
            features.append((cnt.FEATURE_AGGREGATOR, None))

        # view resource
        vr = viewresource.ConnectionListResource()
        top_resource.children[NSI_RESOURCE].putChild('connections', vr)

        # rest service
        if vc[config.REST]:
            rest_url = base_url + '/connections'

            rest.setupService(aggr, top_resource, vc.get(config.ALLOWED_HOSTS))

            service_endpoints.append(('REST', rest_url))
            interfaces.append((cnt.OPENNSA_REST, rest_url, None))

        for backend_network_name, no in networks.items():
            nml_resource_name = '{}.nml.xml'.format(backend_network_name)
            nml_url = '%s/NSI/%s' % (base_url, nml_resource_name)

            nml_network = nml.createNMLNetwork(
                no['nrm_ports'], backend_network_name, backend_network_name)
            can_swap_label = no['backend'].connection_manager.canSwapLabel(
                cnt.ETHERNET_VLAN)

            nml_service = nmlservice.NMLService(nml_network, can_swap_label)

            top_resource.children[NSI_RESOURCE].putChild(
                nml_resource_name.encode(), nml_service.resource())

            service_endpoints.append(('NML Topology', nml_url))
            interfaces.append((cnt.NML_SERVICE_TYPE, nml_url, None))

        # discovery service
        discovery_resource_name = b'discovery.xml'
        discovery_url = '%s/NSI/%s' % (base_url,
                                       discovery_resource_name.decode())

        ds = discoveryservice.DiscoveryService(ns_agent.urn(
        ), now, domain_name, opennsa_version, now, network_urns, interfaces, features, provider_registry, link_vector)

        discovery_resource = ds.resource()
        top_resource.children[NSI_RESOURCE].putChild(
            discovery_resource_name, discovery_resource)
        link_vector.callOnUpdate(
            lambda: discovery_resource.updateResource(ds.xml()))

        service_endpoints.append(('Discovery', discovery_url))

        # log service urls
        for service_name, url in service_endpoints:
            log.msg('{:<12} URL: {}'.format(service_name, url))

        factory = server.Site(top_resource)
        factory.log = httplog.logRequest  # default logging is weird, so we do our own

        return factory, ctx_factory

    def startService(self):

        factory, ctx_factory = self.setupServiceFactory()

        if self.vc[config.TLS]:
            internet.SSLServer(
                self.vc[config.PORT], factory, ctx_factory).setServiceParent(self)
        else:
            internet.TCPServer(self.vc[config.PORT],
                               factory).setServiceParent(self)

        # do not start sub-services until we have started this one
        twistedservice.MultiService.startService(self)

        log.msg('OpenNSA service started')

    def stopService(self):
        twistedservice.Service.stopService(self)


def createApplication(config_file=config.DEFAULT_CONFIG_FILE, debug=False, payload=False):
    application = twistedservice.Application('OpenNSA')

    try:
        configIns = Config.instance()
        cfg, vc = configIns.read_config(config_file)

        # if log file is empty string use stdout
        if vc[config.LOG_FILE]:
            log_file = open(vc[config.LOG_FILE], 'a')
        else:
            import sys
            log_file = sys.stdout

        nsa_service = OpenNSAService(vc)
        nsa_service.setServiceParent(application)

        application.setComponent(log.ILogObserver, logging.DebugLogObserver(
            log_file, debug, payload=payload).emit)
        return application

    except config.ConfigurationError as e:
        import sys
        sys.stderr.write("Configuration error: %s\n" % e)
        sys.exit(1)
