# Fetches discovory documents from other nsas

from xml.etree import cElementTree as ET

from twisted.python import log
from twisted.internet import defer, task, reactor
from twisted.application import service

from opennsa import nsa, constants as cnt
from opennsa.protocols.shared import httpclient
from opennsa.discovery.bindings import discovery
from opennsa.topology import nmlxml
from opennsa.topology.nmlxml import _baseName # nasty but I need it
from opennsa.topology import linknode


LOG_SYSTEM = 'discovery.Fetcher'

# Exponenetial backoff (x2) is used, for fetch intervals
FETCH_INTERVAL_MIN = 10 # seconds
FETCH_INTERVAL_MAX = 3600 # seconds - 3600 seconds = 1 hour



class FetcherService(service.Service):

    def __init__(self, link_node, nrm_ports, peers, provider_registry, ctx_factory=None):
        for peer in peers:
            assert peer.url.startswith('http'), 'Peer URL %s does not start with http' % peer.url

        self.link_node = link_node
        self.nrm_ports = nrm_ports
        self.peers = peers
        self.provider_registry = provider_registry
        self.ctx_factory = ctx_factory

        self.call = task.LoopingCall(self.fetchDocuments)


    def startService(self):
        # we use half, as it is doubled on first run
        reactor.callWhenRunning(self.call.start, FETCH_INTERVAL_MIN // 2)
        service.Service.startService(self)


    def stopService(self):
        self.call.stop()
        service.Service.stopService(self)


    def fetchDocuments(self):
        log.msg('Fetching %i documents.' % len(self.peers), system=LOG_SYSTEM)

        defs = []
        for peer in self.peers:
            log.msg('Fetching %s' % peer.url, debug=True, system=LOG_SYSTEM)
            d = httpclient.httpRequest(peer.url, '', {}, 'GET', timeout=10, ctx_factory=self.ctx_factory)
            d.addCallbacks(self.gotDocument, self.retrievalFailed, callbackArgs=(peer,), errbackArgs=(peer,))
            defs.append(d)

        def updateInterval(passthrough):
            self.call.interval = min(self.call.interval ** 2, FETCH_INTERVAL_MAX)
            return passthrough

        if defs:
            return defer.DeferredList(defs).addBoth(updateInterval)


    def gotDocument(self, result, peer):
        log.msg('Got NSA description from %s (%i bytes)' % (peer.url, len(result)), debug=True, system=LOG_SYSTEM)
        try:
            nsa_description = discovery.parse(result)

            nsa_id = nsa_description.id_

            cs_service_url = None
            nml_service_url = None
            for i in nsa_description.interface:
                if i.type_ == cnt.CS2_PROVIDER:
                    cs_service_url = i.href
                elif i.type_ == cnt.CS2_SERVICE_TYPE and cs_service_url is None: # compat, only overwrite if cs prov not specified
                    cs_service_url = i.href

                if i.type_ == cnt.NML_SERVICE_TYPE:
                    nml_service_url = i.href


            if cs_service_url is None:
                log.msg('NSA description does not have CS interface url, discarding description', system=LOG_SYSTEM)
                return

            network_ids = [ _baseName(nid) for nid in nsa_description.networkId if nid.startswith(cnt.URN_OGF_PREFIX) ] # silent discard weird stuff

            nsi_agent = nsa.NetworkServiceAgent( _baseName(nsa_id), cs_service_url, cnt.CS2_SERVICE_TYPE)

            self.provider_registry.spawnProvider(nsi_agent, network_ids)

            for network_id in network_ids:
                if not network_id in self.link_node.nodes:
                    log.msg("Adding empty node %s" % network_id, debug=True, system=LOG_SYSTEM)
                    self.link_node.addNode( linknode.Node(network_id) )

            # there is lots of other stuff in the nsa description but we don't really use it

            # should fetch the nml and parse demarcation ports
            if nml_service_url is not None:
                d = httpclient.httpRequest(nml_service_url, '', {}, 'GET', timeout=10, ctx_factory=self.ctx_factory)
                d.addCallbacks(self.gotNMLDocument, self.nmlRetrievalFailed, callbackArgs=(nsa_id,), errbackArgs=(nsa_id, nml_service_url))


        except Exception as e:
            log.msg('Error parsing NSA description from url %s. Reason %s' % (peer.url, str(e)), system=LOG_SYSTEM)
            import traceback
            traceback.print_exc()


    def retrievalFailed(self, result, peer):
        log.msg('Topology retrieval failed for %s. Reason: %s.' % (peer.url, result.getErrorMessage()), system=LOG_SYSTEM)


    def gotNMLDocument(self, result, nsa_id):

        doc = ET.fromstring(result)
        nml_network = nmlxml.parseNMLTopology(doc)

        for bd in nml_network.bidirectional_ports:
            if bd.outbound_port.remote_port is not None:
                remote_network = bd.outbound_port.remote_port.rsplit(':',1)[0]
                remote_port    = bd.outbound_port.remote_port.rsplit(':',1)[1].rsplit('-',1)[0] # hack on, won't work everywhere
                label = bd.outbound_port._label
                log.msg("Adding port %s:%s -> %s" % (nml_network.name, bd.name, remote_network), debug=True, system=LOG_SYSTEM)
                self.link_node.nodes[nml_network.id_].addPort(bd.name, label, remote_network, remote_port)


    def nmlRetrievalFailed(self, result, nsa_id, nml_service_url):
        log.msg('NML service retrieval failed for %s/%s. Reason: %s.' % (nsa_id, nml_service_url, result.getErrorMessage()), system=LOG_SYSTEM)

