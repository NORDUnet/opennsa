"""
High-level functionality for creating clients and services in OpenNSA.
"""

from twisted.python import log
from twisted.web import resource, server
from twisted.application import internet, service as twistedservice

from opennsa import config, logging, nsa, database, aggregator, viewresource
from opennsa.topology import nrmparser, nml, http as nmlhttp
from opennsa.protocols import nsi2, discovery



def setupBackend(backend_conf, network_name, parent_requester):

    for backend_name, cfg in backend_conf.items():
        backend_type = cfg['_backend_type']
        bc = cfg.copy()
        del bc['_backend_type']

        if backend_type == config.BLOCK_DUD:
            from opennsa.backends import dud
            return dud.DUDNSIBackend(network_name, parent_requester)

        elif backend_type == config.BLOCK_JUNOS:
            from opennsa.backends import junos
            return junos.JunOSBackend(network_name, bc.items())

        elif backend_type == config.BLOCK_FORCE10:
            from opennsa.backends import force10
            return force10.Force10Backend(network_name, bc.items())

        elif backend_type == config.BLOCK_ARGIA:
            from opennsa.backends import argia
            return argia.ArgiaBackend(network_name, bc.items())

        elif backend_type == config.BLOCK_BROCADE:
            from opennsa.backends import brocade
            return brocade.BrocadeBackend(network_name, bc.items())

        elif backend_type == config.BLOCK_DELL:
            from opennsa.backends import dell
            return dell.DellBackend(network_name, bc.items())

        elif backend_type == config.BLOCK_NCSVPN:
            from opennsa.backends import ncsvpn
            return ncsvpn.NCSVPNBackend(network_name, parent_requester, bc.items())

        else:
            raise config.ConfigurationError('No backend specified')


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
        nsa_endpoint = base_protocol + vc[config.HOST] + ':' + str(vc[config.PORT]) + '/NSI/CS2' # hardcode for now
        ns_agent = nsa.NetworkServiceAgent(network_name, nsa_endpoint)

        topo_source = open( vc[config.NRM_MAP_FILE] ) if type(vc[config.NRM_MAP_FILE]) is str else vc[config.NRM_MAP_FILE] # wee bit hackish

        network, pim = nrmparser.parseTopologySpec( topo_source, network_name, ns_agent)
        topology = nml.Topology()
        topology.addNetwork(network)

        top_resource = resource.Resource()

        providers = { ns_agent.urn() : None }

        aggr = aggregator.Aggregator(network_name, ns_agent, topology, None, providers) # set requester later

        backend_service = setupBackend(vc['backend'], network_name, aggr)
        backend_service.setServiceParent(self)

        providers[ ns_agent.urn() ] = backend_service

        discovery.setupDiscoveryService(None, top_resource)

        pc = nsi2.setupProvider(aggr, top_resource)
        aggr.parent_requester = pc

        vr = viewresource.ConnectionListResource(aggr)
        top_resource.children['NSI'].putChild('connections', vr)

        topology_resource = resource.Resource()
        topology_resource.putChild(vc[config.NETWORK_NAME] + '.xml', nmlhttp.TopologyResource(network))

        top_resource.children['NSI'].putChild('topology', topology_resource)

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

