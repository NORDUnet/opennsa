# Fetches topology representations from other

import StringIO

from twisted.python import log
from twisted.internet import defer, task, reactor
from twisted.application import service

from opennsa.protocols.shared import httpclient
from opennsa.topology import nmlxml


LOG_SYSTEM = 'topology.Fetcher'

FETCH_INTERVAL = 1200 # seconds



class FetcherService(service.Service):

    def __init__(self, route_vectors, topology, peers, provider_registry, ctx_factory=None):
        for peer in peers:
            assert peer.url.startswith('http'), 'Peer URL %s does not start with http' % peer.url

        self.route_vectors = route_vectors
        self.topology = topology
        self.peers = peers
        self.provider_registry = provider_registry
        self.ctx_factory = ctx_factory

        self.call = task.LoopingCall(self.fetchTopologies)


    def startService(self):
        reactor.callWhenRunning(self.call.start, FETCH_INTERVAL)
        service.Service.startService(self)


    def stopService(self):
        self.call.stop()
        for delayed_call in self.blacklist.values():
            delayed_call.cancel()
        service.Service.stopService(self)


    def fetchTopologies(self):
        log.msg('Fetching %i topologies.' % len(self.peers), system=LOG_SYSTEM)

        defs = []
        for peer in self.peers:
            log.msg('Fetching %s' % peer.url, debug=True, system=LOG_SYSTEM)
            d = httpclient.httpRequest(peer.url, '', {}, 'GET', timeout=10, ctx_factory=self.ctx_factory)
            d.addCallbacks(self.gotTopology, self.retrievalFailed, callbackArgs=(peer,), errbackArgs=(peer,))
            defs.append(d)

        if defs:
            return defer.DeferredList(defs)


    def gotTopology(self, result, peer):
        log.msg('Got topology for %s (%i bytes)' % (peer.url, len(result)), debug=True, system=LOG_SYSTEM)
        try:
            nsa_id, nsi_agent, nml_topos, vectors = nmlxml.parseNSITopology(StringIO.StringIO(result))

            topology_ids = [ nt.id_ for nt in nml_topos ]
            self.route_vectors.updateVector(nsa_id, peer.cost, topology_ids, vectors)
            for topo in nml_topos:
                self.topology.updateNetwork(topo, nsi_agent)
            self.provider_registry.spawnProvider(nsi_agent)

        except Exception as e:
            log.msg('Error parsing topology from url %s. Reason %s' % (peer.url, str(e)), system=LOG_SYSTEM)
            import traceback
            traceback.print_exc()


    def retrievalFailed(self, result, peer):
        log.msg('Topology retrieval failed for %s. Reason: %s.' % (peer.url, result.getErrorMessage()), system=LOG_SYSTEM)


