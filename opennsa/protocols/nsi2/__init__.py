"""
Various protocol initialization.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

from twisted.web import resource, server

from opennsa.protocols.shared import soapresource

from opennsa.protocols.nsi2 import providerservice, providerclient, provider, \
                                   requesterservice, requesterclient, requester



def setupProvider(child_provider, top_resource, tls=False, ctx_factory=None, allowed_hosts=None):

    soap_resource = soapresource.setupSOAPResource(top_resource, b'CS2', allowed_hosts=allowed_hosts)

    provider_client = providerclient.ProviderClient(ctx_factory)

    nsi2_provider = provider.Provider(child_provider, provider_client)

    providerservice.ProviderService(soap_resource, nsi2_provider)

    return nsi2_provider


def setupRequesterClient(top_resource, host, port, service_endpoint, resource_name, tls=False, ctx_factory=None, authz_header=None):

    proto_scheme = 'https://' if tls else 'http://'
    service_url = proto_scheme + '%s:%i/NSI/services/%s' % (host,port, resource_name.decode())

    requester_client = requesterclient.RequesterClient(service_endpoint, service_url, ctx_factory=ctx_factory, authz_header=authz_header)
    return requester_client


def setupRequesterPair(top_resource, host, port, service_endpoint, nsi_requester, resource_name=None, tls=False, ctx_factory=None):

    resource_name = resource_name or b'RequesterService2'

    requester_client = setupRequesterClient(top_resource, host, port, service_endpoint, resource_name=resource_name, tls=tls, ctx_factory=ctx_factory)

    soap_resource = soapresource.setupSOAPResource(top_resource, resource_name)
    requesterservice.RequesterService(soap_resource, nsi_requester)

    return requester_client


def createRequester(host, port, service_endpoint, resource_name=None, tls=False, ctx_factory=None, authz_header=None, callback_timeout=None):

    resource_name = resource_name or b'RequesterService2'

    top_resource = resource.Resource()

    requester_client = setupRequesterClient(top_resource, host, port, service_endpoint, resource_name=resource_name, tls=tls, ctx_factory=ctx_factory, authz_header=authz_header)

    nsi_requester = requester.Requester(requester_client, callback_timeout=callback_timeout)

    soap_resource = soapresource.setupSOAPResource(top_resource, resource_name)
    requesterservice.RequesterService(soap_resource, nsi_requester)

    site = server.Site(top_resource, logPath='/dev/null')
    return nsi_requester, site

