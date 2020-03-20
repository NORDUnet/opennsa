"""
Registry for tracking providers dynamically in OpenNSA.

Keeping track of providers in a dynamical way in an NSI implementation is a
huge pain in the ass. This is a combination of things, such as seperate
identities and endpoints, callbacks, and the combination of local providers.

The class ProviderRegistry tries to keep it a bit sane.
"""

from twisted.python import log

from opennsa import error

LOG_SYSTEM = 'providerregistry'


class ProviderRegistry(object):

    def __init__(self, provider_factories):
        # This design might have a small problem removing old entries
        # But I think the old had the same issue, and it is not done currently
        self.providers = {} # network_id -> provider
        self.provider_urns = {} # network_id -> provider_urn
        # in theory the latter mapping might not be needed, but it is hard to do without
        self.provider_factories = provider_factories # { provider_type : provider_spawn_func }


    def addProvider(self, nsi_agent_urn, network_id, provider):
        """
        Directly add a provider. Probably only needed by setup.py
        """
        if network_id in self.providers:
            raise ValueError('Provider for network {} already registered')

        log.msg('Adding new provider for network {}, nsa urn {}'.format(network_id, nsi_agent_urn))
        self.providers[network_id] = provider
        self.provider_urns[network_id] = nsi_agent_urn


    def getProvider(self, network_id):
        """
        Get a provider from a network id
        """
        if network_id.endswith(':nsa'):
            raise ValueError('look like you were trying to a provider via an nsa id')

        try:
            return self.providers[network_id]
        except KeyError:
            log.msg('Cannot provider for network {}, have providers for {}'.format(network_id, ','.join(self.providers.keys())), debug=True, system=LOG_SYSTEM)
            raise error.STPResolutionError('Could not resolve a provider for network %s' % network_id)


    def getProviderURN(self, network_id):
        return self.provider_urns[network_id]


    def spawnProvider(self, nsi_agent, network_id):
        """
        Create a new provider, from an NSI agent.
        ServiceType must exist on the NSI agent, and a factory for the type available.
        """
        assert type(network_id) is str, 'network_id must be a string, got {}'.format(type(network_id))
        if network_id in self.providers:
            log.msg('Skipping provider spawn for %s (already exists)' % nsi_agent, debug=True, system=LOG_SYSTEM)
            return self.providers[network_id]

        if nsi_agent.urn() in self.provider_urns.values():
            log.msg('Provider for {} already exists, re-using'.format(nsi_agent.urn()))
            for other_network_id, provider_urn in self.provider_urns.items():
                if provider_urn == nsi_agent.urn():
                    existing_provider = self.providers[other_network_id]
                    self.addProvider(nsi_agent.urn(), network_id, existing_provider)
                    return
            else:
                log.msg('Did not find an existing provider for {}, should not happen'.format(nsi_agent.urn()))
                return

        factory = self.provider_factories[ nsi_agent.getServiceType() ]
        provisioner = factory(nsi_agent)

        self.addProvider(nsi_agent.urn(), network_id, provisioner)
        log.msg('Spawned new provider for %s' % nsi_agent, system=LOG_SYSTEM)

        return provisioner

