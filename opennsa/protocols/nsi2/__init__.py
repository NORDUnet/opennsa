"""
Various protocol initialization.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

from twisted.web import resource, server

from opennsa.protocols.shared import resource as soapresource

from opennsa.protocols.nsi2 import providerservice, providerclient, provider, \
                                   requesterservice, requesterclient, requester



def setupProvider(nsi_service, top_resource, service_provider, host, port, tls=False, ctx_factory=None):

    soap_resource = soapresource.setupSOAPResource(top_resource, 'CS2')

#    service_registry.registerEventHandler(registry.RESERVE,   nsi_requester.reserve,    registry.NSI2_CLIENT)
#    service_registry.registerEventHandler(registry.PROVISION, nsi_requester.provision,  registry.NSI2_CLIENT)
#    service_registry.registerEventHandler(registry.RELEASE,   nsi_requester.release,    registry.NSI2_CLIENT)
#    service_registry.registerEventHandler(registry.TERMINATE, nsi_requester.terminate,  registry.NSI2_CLIENT)
#    service_registry.registerEventHandler(registry.QUERY,     nsi_requester.query,      registry.NSI2_CLIENT)

    provider_client = providerclient.ProviderClient(ctx_factory)

    nsi2_provider = provider.Provider(service_provider)

    providerservice.ProviderService(soap_resource, nsi2_provider)

    return provider_client


def setupRequester(top_resource, host, port, tls=False, ctx_factory=None, callback_timeout=None):

    resource_name = 'RequesterService2'

    # copied from nsi1.__init__
    def _createServiceURL(host, port, tls=False):
        proto_scheme = 'https://' if tls else 'http://'
        service_url = proto_scheme + '%s:%i/NSI/services/%s' % (host,port, resource_name)
        return service_url

    service_url = _createServiceURL(host, port, tls)

    soap_resource = soapresource.setupSOAPResource(top_resource, resource_name)

    requester_client = requesterclient.RequesterClient(service_url)

    nsi_requester = requester.Requester(requester_client, callback_timeout=callback_timeout)

    requester_service = requesterservice.RequesterService(soap_resource, nsi_requester)

    return nsi_requester


# copied from nsi1.__init__
def createRequesterClient(host, port, tls=False, ctx_factory=None, callback_timeout=None):

    top_resource = resource.Resource()
    nsi_requester = setupRequester(top_resource, host, port, tls, ctx_factory, callback_timeout)
    site = server.Site(top_resource, logPath='/dev/null')
    return nsi_requester, site


