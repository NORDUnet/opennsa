"""
Discovery service client.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

import StringIO

from opennsa.protocols.shared import minisoap, httpclient
from opennsa.protocols.discovery import bindings



DISCOVERY_TYPES_NS = "http://schemas.ogf.org/nsi/2012/03/discovery/types"

REQUEST_DETAILED = 'Detailed'
REQUEST_SUMMARY  = 'Summary'

QUERY_SERVICES = '"http://schemas.ogf.org/nsi/2012/03/discovery/service/queryServices"'



class DiscoveryClient:

    def __init__(self, ctx_factory=None):

        self.ctx_factory = ctx_factory


    def queryNSA(self, service_url, request_type=REQUEST_DETAILED):


        def errReply(err):
            print err
            print err.value.response
            return err

        def gotReply(soap_data):
            print "GOT REPLY\n", soap_data

        #payload = soap.createQueryNSAPayload()
        #print payload
        #print "=="

        q = bindings.QueryNsaRequestType()

        f = StringIO.StringIO()
        q.export(f,0, namespacedef_='xmlns:tns="%s"' % DISCOVERY_TYPES_NS)
        body_payload = f.getvalue()

        payload = minisoap.createSoapPayload(body_payload)


        f = httpclient.httpRequest(service_url, QUERY_SERVICES, payload, ctx_factory=self.ctx_factory)
        f.deferred.addCallbacks(gotReply, errReply)

        return f.deferred

