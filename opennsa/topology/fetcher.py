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

    def __init__(self, peering_entries, topology, provider_registry, ctx_factory=None):
        for purl in peering_entries:
            assert purl.startswith('http'), 'Peer URL %s does not start with http' % topo_url

        self.peering_entries = peering_entries
        self.topology = topology
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
        log.msg('Fetching %i topologies.' % len(self.peering_entries), system=LOG_SYSTEM)

        defs = []
        for purl in self.peering_entries:
            log.msg('Fetching %s' % purl, debug=True, system=LOG_SYSTEM)
            d = httpclient.httpRequest(purl, '', {}, 'GET', timeout=10, ctx_factory=self.ctx_factory)
            d.addCallbacks(self.gotTopology, self.retrievalFailed, callbackArgs=(purl,), errbackArgs=(purl,))
            defs.append(d)

        if defs:
            return defer.DeferredList(defs)


    def gotTopology(self, result, purl):
        log.msg('Got topology for %s (%i bytes)' % (purl, len(result)), debug=True, system=LOG_SYSTEM)
        try:
            nsi_agent, nml_network = nmlxml.parseNSITopology(StringIO.StringIO(result))
            # here we could do some version checking first
            self.topology.updateNetwork(nml_network, nsi_agent)
            log.msg('Topology for %s updated' % nml_network.name, system=LOG_SYSTEM)
            self.provider_registry.spawnProvider(nsi_agent)

        except Exception as e:
            log.msg('Error parsing topology from url %s. Reason %s' % (purl, str(e)), system=LOG_SYSTEM)
            self.blacklistNetwork(network_name)
            import traceback
            traceback.print_exc()


    def retrievalFailed(self, result, purl):
        log.msg('Topology retrieval failed for %s. Reason: %s.' % (purl, result.getErrorMessage()), system=LOG_SYSTEM)


