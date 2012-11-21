"""
Discovery service client.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""


from opennsa.protocols.shared import twistedsuds

from opennsa.protocols.discovery import soap


WSDL_DISCOVERY = 'file://%s/ogf_nsi_discovery_provider_v1_0.wsdl'

DISCOVERY_NS = "http://schemas.ogf.org/nsi/2012/03/discovery/types"

QUERY_REQUEST_TYPE = '{%s}QueryNsaRequestType' % DISCOVERY_NS

REQUEST_DETAILED = 'Detailed'
REQUEST_SUMMARY  = 'Summary'


QUERY_SERVICES = '"http://schemas.ogf.org/nsi/2012/03/discovery/service/queryServices"'



class DiscoveryClient:

    # SUDS b0rks on the WSDL, creating nested requestType elements, so we use manual construction instead.

    def __init__(self, wsdl_dir, ctx_factory=None):

        self.ctx_factory = ctx_factory


    def queryNSA(self, service_url, request_type=REQUEST_DETAILED):

#        req = self.client.createType(QUERY_REQUEST_TYPE)
#        req.requestType = request_type
#        d = self.client.invoke(service_url, 'queryNSA', req)

        def gotReply(soap_data):
            print "GOT REPLY\n", soap_data

        payload = soap.createQueryNSAPayload()

        d, factory = twistedsuds._httpRequest(service_url, QUERY_SERVICES, payload, ctx_factory=self.ctx_factory)
        d.addCallback(gotReply)

        return d


