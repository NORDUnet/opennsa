"""
NSI SOAP stuff.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from twisted.python import log
from twisted.application import internet, service
from twisted.web import resource, server

from suds.sax import parser
from suds.umx.typed import Typed as UmxTyped
from suds.bindings import document
from suds.client import Client


GENERIC_RESPONSE_TYPE = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:ns0="http://schemas.ogf.org/nsi/2011/07/connection/interface" xmlns:ns1="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
    <SOAP-ENV:Header/>
    <ns1:Body>
        <ns0:GenericResponseType/>
    </ns1:Body>
</SOAP-ENV:Envelope>
"""

NSI_WSDL            = 'file:///home/htj/nsi/suds-ex/ogf_nsi_connection_service_v1_0.wsdl'
NSI_TYPE_NAMESPACE  = 'http://schemas.ogf.org/nsi/2011/07/connection/types'
ENV_NS              = ('SOAP-ENV', 'http://schemas.xmlsoap.org/soap/envelope/')

# these are the soap actions and corresponding types that can be received by the service
REQUEST_TYPES = {
    '"http://schemas.ogf.org/nsi/2011/07/connection/service/reserve"'               : 'ReserveType',
    '"http://schemas.ogf.org/nsi/2011/07/connection/service/reserveConfirmed"'      : 'ReserveConfirmedType',
    '"http://schemas.ogf.org/nsi/2011/07/connection/service/reserveFailed"'         : 'ReserveFailedRequestType',
    '"http://schemas.ogf.org/nsi/2011/07/connection/service/provision"'             : 'ProvisionRequestType',
#    '"http://schemas.ogf.org/nsi/2011/07/connection/service/provisionConfirmed"',
#    '"http://schemas.ogf.org/nsi/2011/07/connection/service/provisionFailed"',
    '"http://schemas.ogf.org/nsi/2011/07/connection/service/release"'               : 'ReleaseRequestType',
#    '"http://schemas.ogf.org/nsi/2011/07/connection/service/releaseConfirmed"',
#    '"http://schemas.ogf.org/nsi/2011/07/connection/service/releaseFailed"',
    '"http://schemas.ogf.org/nsi/2011/07/connection/service/cancel"'                : 'CancelRequestType',
#    '"http://schemas.ogf.org/nsi/2011/07/connection/service/cancelConfirmed"',
#    '"http://schemas.ogf.org/nsi/2011/07/connection/service/cancelFailed"',
    '"http://schemas.ogf.org/nsi/2011/07/connection/service/query"'                 : 'QueryRequestType'
#    '"http://schemas.ogf.org/nsi/2011/07/connection/service/queryConfirmed"',
#    '"http://schemas.ogf.org/nsi/2011/07/connection/service/queryFailed"'
}


ACCEPTED_SOAP_ACTIONS = REQUEST_TYPES.keys()



class NSIWSDecoder:

    def __init__(self, wsdl=None):
        self.client = Client(wsdl or NSI_WSDL)
        binding = document.Document(self.client.wsdl)
        self.schema = binding.wsdl.schema
        self.umx = UmxTyped(self.schema)


    def decodeRequest(self, soap_action, content):

        # parse request
        sax = parser.Parser()
        root = sax.parse(content)
        soapenv = root.getChild('Envelope')
        soapenv.promotePrefixes()
        soapbody = soapenv.getChild('Body')

        # check for fault
        fault = soapbody.getChild('Fault', ENV_NS)
        if fault is not None:
            raise NotImplementedError('Got fault in NSI SOAP service request decoding (should this happen?)')

        # decode request
        nodes = soapbody.children[0]

        trans_id = nodes[0].text
        reply_to = nodes[1].text
        request  = nodes[2]

        req_type = REQUEST_TYPES[soap_action]
        schema_type = self.schema.types[(req_type, NSI_TYPE_NAMESPACE)]

        r = self.umx.process(request, schema_type)

        return trans_id, reply_to, r



    def encodeRequest(self, trans_id):

        #print self.client
        #response = self.client.factory.create('ns0:GenericResponseType')
        #print res

#        method = client.service.reserve
#        b = document.Document(client.wsdl)
#
#        schema = b.wsdl.schema
#
#        rrt = schema.types[res_type]
#
#        args = (trans_id, reply_to, res)
#        soapenv = b.get_message(method.method, args, kwargs={})


        return ''

