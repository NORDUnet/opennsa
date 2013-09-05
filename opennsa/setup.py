"""
High-level functionality for creating clients and services in OpenNSA.
"""

from twisted.python import log
from twisted.web import resource, server
from twisted.application import internet, service as twistedservice

from opennsa import config, logging, nsa, database, aggregator, viewresource
from opennsa.topology import nrmparser, nml, http as nmlhttp, fetcher
from opennsa.protocols import nsi2, discovery



def setupBackend(backend_cfg, network_name, network_topology, parent_requester, port_map):

    bc = backend_cfg.copy()
    backend_type = backend_cfg.pop('_backend_type')

    if backend_type == config.BLOCK_DUD:
        from opennsa.backends import dud
        BackendConstructer = dud.DUDNSIBackend

# These are not yet ported for the new backend
#    elif backend_type == config.BLOCK_JUNOS:
#        from opennsa.backends import junos
#        return junos.JunOSBackend(network_name, parent_requester, port_map, bc.items())
#
#    elif backend_type == config.BLOCK_FORCE10:
#        from opennsa.backends import force10
#        return force10.Force10Backend(network_name, parent_requester, port_map, bc.items())
#
#    elif backend_type == config.BLOCK_ARGIA:
#        from opennsa.backends import argia
#        return argia.ArgiaBackend(network_name, bc.items())

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

    b = BackendConstructer(network_name, network_topology, parent_requester, port_map, bc)
    return b



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

        if vc[config.HOST] is None:
            import socket
            vc[config.HOST] = socket.getfqdn()

        # database
        database.setupDatabase(vc[config.DATABASE], vc[config.DATABASE_USER], vc[config.DATABASE_PASSWORD])

        # setup topology

        network_name = vc[config.NETWORK_NAME]

        base_protocol = 'https://' if vc[config.TLS] else 'http://'
        nsa_endpoint = base_protocol + vc[config.HOST] + ':' + str(vc[config.PORT]) + '/NSI/services/CS2' # hardcode for now
        ns_agent = nsa.NetworkServiceAgent(network_name + ':nsa', nsa_endpoint)

        topo_source = open( vc[config.NRM_MAP_FILE] ) if type(vc[config.NRM_MAP_FILE]) is str else vc[config.NRM_MAP_FILE] # wee bit hackish

        network, port_map = nrmparser.parseTopologySpec(topo_source, network_name)
        topology = nml.Topology()
        topology.addNetwork(network, ns_agent)

        providers = {} # This is filled out later, consider it a registry

        aggr = aggregator.Aggregator(network_name, ns_agent, topology, None, providers) # set requester later

        # setup backend(s) - for now we only support one

        backend_configs = vc['backend']
        if len(backend_configs) > 1:
            raise config.ConfigurationError('Only one backend supported for now. Multiple will probably come later.')

        backend_cfg = backend_configs.values()[0]

        network_topology = topology.getNetwork(network_name)

        backend_service = setupBackend(backend_cfg, network_name, network_topology, aggr, port_map)
        backend_service.setServiceParent(self)

        providers[ ns_agent.urn() ] = backend_service

        # done with backend, now fetcher

        if vc[config.PEERS]:
            fetcher_service = fetcher.FetcherService(vc[config.PEERS], topology)
            fetcher_service.setServiceParent(self)

        # wire up the http stuff

        top_resource = resource.Resource()
        discovery.setupDiscoveryService(None, top_resource)

        pc = nsi2.setupProvider(aggr, top_resource)
        aggr.parent_requester = pc

        vr = viewresource.ConnectionListResource(aggr)
        top_resource.children['NSI'].putChild('connections', vr)

        topology_resource = resource.Resource()
        topology_resource.putChild(vc[config.NETWORK_NAME] + '.xml', nmlhttp.TopologyResource(ns_agent, network))

        top_resource.children['NSI'].putChild('topology', topology_resource)

        proto_scheme = 'https' if vc[config.TLS] else 'http'
        log.msg('Provider URL: %s://%s:%s/NSI/services/CS2' % (proto_scheme, vc[config.HOST], vc[config.PORT] ) )
        log.msg('Topology URL: %s://%s:%s/NSI/topology/%s.xml' % (proto_scheme, vc[config.HOST], vc[config.PORT], vc[config.NETWORK_NAME]) )

        factory = server.Site(top_resource, logPath='/dev/null')


        if vc[config.TLS]:
            from opennsa import ctxfactory
            ctx_factory = ctxfactory.ContextFactory(vc[config.KEY], vc[config.CERTIFICATE], vc[config.CERTIFICATE_DIR], vc[config.VERIFY_CERT])
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

