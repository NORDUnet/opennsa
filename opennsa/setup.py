"""
High-level functionality for creating clients and services in OpenNSA.
"""
import os
import hashlib
import datetime

from twisted.python import log
from twisted.web import resource, server
from twisted.application import internet, service as twistedservice

from opennsa import __version__ as version

from opennsa import config, logging, constants as cnt, nsa, provreg, database, aggregator, viewresource
from opennsa.topology import nrm, nml, linkvector, service as nmlservice
from opennsa.protocols.shared import httplog
from opennsa.discovery import service as discoveryservice, fetcher
from opennsa.protocols import nsi2



def setupBackend(backend_cfg, network_name, nrm_ports, parent_requester):

    bc = backend_cfg.copy()
    backend_type = backend_cfg.pop('_backend_type')

    if backend_type == config.BLOCK_DUD:
        from opennsa.backends import dud
        BackendConstructer = dud.DUDNSIBackend

# These are not yet ported for the new backend
#    elif backend_type == config.BLOCK_JUNOS:
#        from opennsa.backends import junos
#        return junos.JunOSBackend(network_name, parent_requester, port_map, bc.items())

    elif backend_type == config.BLOCK_FORCE10:
        from opennsa.backends import force10
        BackendConstructer = force10.Force10Backend

    elif backend_type == config.BLOCK_JUNIPER_EX:
        from opennsa.backends import juniperex
        BackendConstructer = juniperex.JuniperEXBackend

    elif backend_type == config.BLOCK_BROCADE:
        from opennsa.backends import brocade
        BackendConstructer = brocade.BrocadeBackend

#    elif backend_type == config.BLOCK_DELL:
#        from opennsa.backends import dell
#        return dell.DellBackend(network_name, bc.items())

    elif backend_type == config.BLOCK_NCSVPN:
        from opennsa.backends import ncsvpn
        BackendConstructer = ncsvpn.NCSVPNBackend

    else:
        raise config.ConfigurationError('No backend specified')

    b = BackendConstructer(network_name, nrm_ports, parent_requester, bc)
    return b



def setupTLSContext(vc):

    # ssl/tls contxt
    if vc[config.TLS]:
        from opennsa import ctxfactory
        ctx_factory = ctxfactory.ContextFactory(vc[config.KEY], vc[config.CERTIFICATE], vc[config.CERTIFICATE_DIR], vc[config.VERIFY_CERT])
    elif os.path.isdir(vc[config.CERTIFICATE_DIR]):
        # we can at least create a context
        from opennsa import ctxfactory
        ctx_factory = ctxfactory.RequestContextFactory(vc[config.CERTIFICATE_DIR], vc[config.VERIFY_CERT])
    else:
        ctx_factory = None

    return ctx_factory



class CS2RequesterCreator:

    def __init__(self, top_resource, aggregator, host, port, tls, ctx_factory):
        self.top_resource = top_resource
        self.aggregator   = aggregator
        self.host         = host
        self.port         = port
        self.tls          = tls
        self.ctx_factory  = ctx_factory


    def create(self, nsi_agent):

        resource_name = 'RequesterService2-' + hashlib.sha1(nsi_agent.urn() + nsi_agent.endpoint).hexdigest()
        return nsi2.setupRequesterPair(self.top_resource, self.host, self.port, nsi_agent.endpoint, self.aggregator,
                                       resource_name, tls=self.tls, ctx_factory=self.ctx_factory)



class OpenNSAService(twistedservice.MultiService):

    def __init__(self, vc):
        twistedservice.MultiService.__init__(self)
        self.vc = vc


    def startService(self):
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
        database.setupDatabase(vc[config.DATABASE], vc[config.DATABASE_USER], vc[config.DATABASE_PASSWORD])

        # base names
        base_name = vc[config.NETWORK_NAME]
        network_name = base_name + ':topology' # because we say so
        nsa_name  = base_name + ':nsa'

        # base url
        base_protocol = 'https://' if vc[config.TLS] else 'http://'
        base_url = base_protocol + vc[config.HOST] + ':' + str(vc[config.PORT])

        # nsi agent
        provider_endpoint = base_url + '/NSI/services/CS2' # hardcode for now
        ns_agent = nsa.NetworkServiceAgent(nsa_name, provider_endpoint, 'local')

        # topology
        nrm_ports = nrm.parsePortSpec( open( vc[config.NRM_MAP_FILE] ) )
        network_topology = nml.createNMLNetwork(nrm_ports, network_name, base_name)

        # route vectors
        link_vector = linkvector.LinkVector( [ network_name ] )
        # hack in link vectors manually, since we don't have a mechanism for updating them automatically
        for np in nrm_ports:
            if np.remote_network is not None:
                link_vector.updateVector(np.name, { np.remote_network : 1 } ) # hack
                for network, cost in np.vectors.items():
                    link_vector.updateVector(np.name, { network : cost })

        ctx_factory = setupTLSContext(vc) # May be None

        # plugin
        if vc[config.PLUGIN]:
            from twisted.python import reflect
            plugin = reflect.namedAny('opennsa.plugins.%s.plugin' % vc[config.PLUGIN])
        else:
            from opennsa.plugin import BasePlugin
            plugin = BasePlugin()
        plugin.init(vc, ctx_factory)

        # the dance to setup dynamic providers right
        top_resource = resource.Resource()
        requester_creator = CS2RequesterCreator(top_resource, None, vc[config.HOST], vc[config.PORT], vc[config.TLS], ctx_factory) # set aggregator later

        provider_registry = provreg.ProviderRegistry({}, { cnt.CS2_SERVICE_TYPE : requester_creator.create } )
        aggr = aggregator.Aggregator(network_name, ns_agent, network_topology, link_vector, None, provider_registry, vc[config.POLICY], plugin ) # set parent requester later

        requester_creator.aggregator = aggr

        pc = nsi2.setupProvider(aggr, top_resource, ctx_factory=ctx_factory, allowed_hosts=vc.get(config.ALLOWED_HOSTS))
        aggr.parent_requester = pc

        if vc[config.REST]:
            from opennsa.protocols import rest
            rest_endpoint = base_url + '/connections'
            rest.setupService(aggr, top_resource, vc.get(config.ALLOWED_HOSTS))

        # setup backend(s) - for now we only support one

        backend_configs = vc['backend']
        if len(backend_configs) > 1:
            raise config.ConfigurationError('Only one backend supported for now. Multiple will probably come later.')

        backend_cfg = backend_configs.values()[0]

        backend_service = setupBackend(backend_cfg, network_topology.id_, nrm_ports, aggr)
        backend_service.setServiceParent(self)
        can_swap_label = backend_service.connection_manager.canSwapLabel(cnt.ETHERNET_VLAN)

        provider_registry.addProvider(ns_agent.urn(), backend_service, [ network_topology.id_ ] )

        # fetcher
        if vc[config.PEERS]:
            fetcher_service = fetcher.FetcherService(link_vector, nrm_ports, vc[config.PEERS], provider_registry, ctx_factory=ctx_factory)
            fetcher_service.setServiceParent(self)

        # wire up the http stuff

        discovery_resource_name = 'discovery.xml'
        nml_resource_name       = base_name + '.nml.xml'
        nml_resource_url        = '%s/NSI/%s' % (base_url, nml_resource_name)

        # discovery service
        name = base_name.split(':')[0] if ':' in base_name else base_name
        opennsa_version = 'OpenNSA-' + version
        networks    = [ cnt.URN_OGF_PREFIX + network_name ]
        interfaces  = [ ( cnt.CS2_PROVIDER, provider_endpoint, None), ( cnt.CS2_SERVICE_TYPE, provider_endpoint, None), (cnt.NML_SERVICE_TYPE, nml_resource_url, None) ]
        features    = [ (cnt.FEATURE_AGGREGATOR, None), (cnt.FEATURE_UPA, None) ]
        ds = discoveryservice.DiscoveryService(ns_agent.urn(), now, name, opennsa_version, now, networks, interfaces, features, provider_registry, link_vector)

        discovery_resource = ds.resource()
        top_resource.children['NSI'].putChild(discovery_resource_name, discovery_resource)
        link_vector.callOnUpdate( lambda : discovery_resource.updateResource ( ds.xml() ))

        # view resource
        vr = viewresource.ConnectionListResource()
        top_resource.children['NSI'].putChild('connections', vr)

        # topology
        nml_service = nmlservice.NMLService(network_topology, can_swap_label)
        top_resource.children['NSI'].putChild(nml_resource_name, nml_service.resource() )

        log.msg('Provider  URL: %s' % provider_endpoint )
        log.msg('Discovery URL: %s/NSI/%s' % (base_url, discovery_resource_name) )
        log.msg('Topology  URL: %s' % (nml_resource_url) )
        if vc[config.REST]:
            log.msg('REST      URL: %s' % rest_endpoint )

        factory = server.Site(top_resource)
        factory.log = httplog.logRequest # default logging is weird, so we do our own

        if vc[config.TLS]:
            internet.SSLServer(vc[config.PORT], factory, ctx_factory).setServiceParent(self)
        else:
            internet.TCPServer(vc[config.PORT], factory).setServiceParent(self)

        # do not start sub-services until we have started this one
        twistedservice.MultiService.startService(self)

        log.msg('OpenNSA service started')


    def stopService(self):
        twistedservice.Service.stopService(self)



def createApplication(config_file=config.DEFAULT_CONFIG_FILE, debug=False, payload=False):

    application = twistedservice.Application('OpenNSA')

    try:

        cfg = config.readConfig(config_file)
        vc = config.readVerifyConfig(cfg)

        # if log file is empty string use stdout
        if vc[config.LOG_FILE]:
            log_file = open(vc[config.LOG_FILE], 'a')
        else:
            import sys
            log_file = sys.stdout

        nsa_service = OpenNSAService(vc)
        nsa_service.setServiceParent(application)

        application.setComponent(log.ILogObserver, logging.DebugLogObserver(log_file, debug, payload=payload).emit)
        return application

    except config.ConfigurationError as e:
        import sys
        sys.stderr.write("Configuration error: %s\n" % e)
        sys.exit(1)

