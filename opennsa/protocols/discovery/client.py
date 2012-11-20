"""
Discovery service client.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""


from opennsa.protocols.shared import twistedsuds


WSDL_DISCOVERY = 'file://%s/ogf_nsi_discovery_provider_v1_0.wsdl'

DISCOVERY_NS = "http://schemas.ogf.org/nsi/2012/03/discovery/types"

QUERY_REQUEST_TYPE = '{%s}QueryNsaRequestType' % DISCOVERY_NS

REQUEST_DETAILED = 'Detailed'
REQUEST_SUMMARY  = 'Summary'



class DiscoveryClient:

    def __init__(self, wsdl_dir, ctx_factory=None):

        self.client = twistedsuds.TwistedSUDSClient(WSDL_DISCOVERY % wsdl_dir, ctx_factory=ctx_factory)


    def queryNSA(self, service_url, request_type=REQUEST_DETAILED):

        req = self.client.createType(QUERY_REQUEST_TYPE)
        print "REQ\n", req

        req.requestType.value = 'Detailed'
#        if request_type is not None:
#            req.requestType = request_type

        print "REQ\n", req

        d = self.client.invoke(service_url, 'queryNSA', req)
        return d

