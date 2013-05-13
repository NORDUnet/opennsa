"""
High-level functionality for creating clients and services in OpenNSA.
"""

from twisted.python import log
from twisted.web import resource, server
from twisted.application import internet, service as twistedservice

from opennsa import config, logging, registry, database, nsiservice, viewresource
from opennsa.topology import nrmparser, nml
from opennsa.protocols import nsi2, discovery



def setupBackend(backend_conf, network_name, service_registry):

    for backend_name, cfg in backend_conf.items():
        backend_type = cfg['_backend_type']
        bc = cfg.copy()
        del bc['_backend_type']

        if backend_type == config.BLOCK_DUD:
            from opennsa.backends import dud
            return dud.DUDNSIBackend(network_name, service_registry)

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

        # database
        database.setupDatabase(vc[config.DATABASE], vc[config.DATABASE_USER], vc[config.DATABASE_PASSWORD])

        # topology
        topology = nml.Topology()
        # need to add check for nrm file, no longer just nrm really
        #ns_agent = 'urn:ogf:network:' + vc[config.NETWORK_NAME] + ':nsa' # fixme
        network = nrmparser.parseTopologySpec( open( vc[config.NRM_MAP_FILE] ), vc[config.NETWORK_NAME])
        topology.addNetwork(network)

        if vc[config.HOST] is None:
            import socket
            vc[config.HOST] = socket.getfqdn()

        ctx_factory = None
        if vc[config.TLS]:
            from opennsa import ctxfactory
            ctx_factory = ctxfactory.ContextFactory(vc[config.KEY], vc[config.CERTIFICATE], vc[config.CERTIFICATE_DIR], vc[config.VERIFY_CERT])

        top_resource = resource.Resource()
        service_registry = registry.ServiceRegistry()

        backend_service = setupBackend(vc['backend'], vc[config.NETWORK_NAME], service_registry)
        backend_service.setServiceParent(self)

        nsi_service  = nsiservice.NSIService(vc[config.NETWORK_NAME], backend_service, service_registry, topology)

        discovery.setupDiscoveryService(None, top_resource)

        nsi2.setupProvider(nsi_service, top_resource, service_registry, vc[config.HOST], vc[config.PORT])

        vr = viewresource.ConnectionListResource(nsi_service)
        top_resource.children['NSI'].putChild('connections', vr)

        factory = server.Site(top_resource, logPath='/dev/null')


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

