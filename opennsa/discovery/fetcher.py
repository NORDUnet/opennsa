# Fetches discovory documents from other nsas

from twisted.python import log
from twisted.internet import defer, task, reactor
from twisted.application import service

from opennsa import nsa, constants as cnt
from opennsa.protocols.shared import httpclient
from opennsa.discovery.bindings import discovery
from opennsa.topology.nmlxml import _baseName # nasty but I need it


LOG_SYSTEM = 'discovery.Fetcher'

FETCH_INTERVAL = 3600 # seconds - 3600 seconds = 1 hour



class FetcherService(service.Service):

    def __init__(self, link_vectors, nrm_ports, peers, provider_registry, ctx_factory=None):
        for peer in peers:
            assert peer.url.startswith('http'), 'Peer URL %s does not start with http' % peer.url

        self.link_vectors = link_vectors
        self.nrm_ports = nrm_ports
        self.peers = peers
        self.provider_registry = provider_registry
        self.ctx_factory = ctx_factory

        self.call = task.LoopingCall(self.fetchDocuments)


    def startService(self):
        reactor.callWhenRunning(self.call.start, FETCH_INTERVAL)
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

        if defs:
            return defer.DeferredList(defs)


    def gotDocument(self, result, peer):
        log.msg('Got NSA description from %s (%i bytes)' % (peer.url, len(result)), debug=True, system=LOG_SYSTEM)
        try:
            nsa_description = discovery.parse(result)

            nsa_id = nsa_description.id_

            cs_service_url = None
            for i in nsa_description.interface:
                if i.type_ == cnt.CS2_PROVIDER:
                    cs_service_url = i.href
                elif i.type_ == cnt.CS2_SERVICE_TYPE and cs_service_url is None: # compat, only overwrite if cs prov not specified
                    cs_service_url = i.href

            if cs_service_url is None:
                log.msg('NSA description does not have CS interface url, discarding description', system=LOG_SYSTEM)
                return

            network_ids = [ _baseName(nid) for nid in nsa_description.networkId if nid.startswith(cnt.URN_OGF_PREFIX) ] # silent discard weird stuff

            nsi_agent = nsa.NetworkServiceAgent( _baseName(nsa_id), cs_service_url, cnt.CS2_SERVICE_TYPE)

            self.provider_registry.spawnProvider(nsi_agent, network_ids)

            # first, build vectors
            vectors = {}
            if nsa_description.other is not None:
                for other in nsa_description.other:
                    if other.topologyReachability:
                        for tr in other.topologyReachability:
                            if tr.uri.startswith(cnt.URN_OGF_PREFIX): # silent discard weird stuff
                                vectors[_baseName(tr.uri)] = tr.cost + 1
            for nid in network_ids:
                vectors[nid] = 1

            # update per-port link vectors
            if vectors:
                for np in self.nrm_ports:
                    if np.remote_network in network_ids:
                        # this may add the vectors to multiple ports (though not likely)
                        self.link_vectors.updateVector(np.name, vectors )

            # there is lots of other stuff in the nsa description but we don't really use it


        except Exception as e:
            log.msg('Error parsing NSA description from url %s. Reason %s' % (peer.url, str(e)), system=LOG_SYSTEM)
            import traceback
            traceback.print_exc()


    def retrievalFailed(self, result, peer):
        log.msg('Topology retrieval failed for %s. Reason: %s.' % (peer.url, result.getErrorMessage()), system=LOG_SYSTEM)


