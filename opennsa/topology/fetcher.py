# Fetches topology representations from other

import time
import StringIO

from twisted.python import log
from twisted.internet import defer, task
from twisted.application import service

from opennsa.protocols.shared import httpclient
from opennsa.topology import nmlxml


LOG_SYSTEM = 'topology.Fetcher'

FETCH_INTERVAL = 20 # seconds, increase for production :-)



class FetcherService(service.Service):

    def __init__(self, peering_entries):
        # peering entries is a list of two-tuples, where each tuple contains
        # a network name and the url of the network topology
        #for network, topo_url in peering_pairs:
        for pe in peering_entries:
            assert len(pe) is 2, 'Peering entry %s is not two-tuple' % pp
            network, topo_url = pe
            assert topo_url.startswith('http'), 'Topology URL %s does not start with http' % topo_url

        self.peering_entries = peering_entries
        self.blacklist = {}

        self.call = task.LoopingCall(self.fetchTopologies)


    def startService(self):
        self.call.start(FETCH_INTERVAL)
        service.Service.startService(self)


    def stopService(self):
        self.call.stop()
        service.Service.stopService(self)


    def blacklist(self, network_name, time=600):
        # blacklist a network for a certain amount of time
        expire_time = int(time.time() + time)
        self.blacklists[network_name] = expire_time


    def getPeeringEntries(self):
        # filters out the blacklisted sites
        pass # implement me



    def fetchTopologies(self):
        log.msg('Fetching topologies. %i sources' % len(self.peering_entries), system=LOG_SYSTEM)

        defs = []
        for network_name, topology_url in self.peering_entries:
            log.msg('Fetchin topology for network %s from %s' % (network_name, topology_url), system=LOG_SYSTEM)
            d = httpclient.httpRequest(topology_url, '', {}, 'GET', timeout=10) # https should perhaps be added sometime
            ca = (network_name, topology_url)
            d.addCallbacks(self.gotTopology, self.retrievalFailed, callbackArgs=ca, errbackArgs=ca)
            defs.append(d)

        if defs:
            return defer.DeferredList(defs)


    def gotTopology(self, result, network_name, topology_url):
        log.msg('Got topology for %s (%i bytes)' % (network_name, len(result)), system=LOG_SYSTEM)
        try:
            nsi_agent, nml_network = nmlxml.parseNSITopology(StringIO.StringIO(result))
        except Exception as e:
            log.msg('Error parsing topology for network %s, url %s. Reason %s' % (network_name, topology_url, str(e)), system=LOG_SYSTEM)
            self.blacklist(network_name)


    def retrievalFailed(self, result, network_name, topology_url):
        log.msg('Topology retrieval for network %s from URL %s failed. Reason %s' % (network_name, topology_url, str(result)), system=LOG_SYSTEM)
        self.blacklist(network_name)

