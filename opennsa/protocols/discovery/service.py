"""
Web Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

#import time
import datetime
from twisted.python import log

#from suds.sax import date as sudsdate

from opennsa import nsa
from opennsa.protocols.shared import sudsservice
from opennsa.protocols.discovery import soap




LOG_SYSTEM = 'protocol.discover.service'

WSDL_DISCOVERY = 'file://%s/ogf_nsi_discovery_provider_v1_0.wsdl'

QUERY_SERVICES = '"http://schemas.ogf.org/nsi/2012/03/discovery/service/queryServices"'

# Hack on!
# Getting SUDS to throw service faults is more or less impossible as it is a client library
# We do this instead
SERVICE_FAULT = """<?xml version='1.0' encoding='UTF-8'?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <soap:Fault xmlns:envelope="http://www.w3.org/2003/05/soap-envelope">
            <faultcode>soap:Server</faultcode>
            <faultstring>%(error_text)s</faultstring>
            <detail>
                <nsi:serviceException xmlns:nsi="http://schemas.ogf.org/nsi/2011/10/connection/interface">
                    <errorId>%(error_id)s</errorId>
                    <text>%(error_text)s</text>
                </nsi:serviceException>
            </detail>
        </soap:Fault>
    </soap:Body>
</soap:Envelope>
"""



class DiscoverService:

    def __init__(self, soap_resource, discoverer, wsdl_dir):

        self.discoverer = discoverer
        self.soap_resource = soap_resource
        self.decoder = sudsservice.WSDLMarshaller(WSDL_DISCOVERY % wsdl_dir)

        self.soap_resource.registerDecoder(QUERY_SERVICES, self.queryServices)


    def _getRequestParameters(self, grt):
        correlation_id  = str(grt.correlationId)
        reply_to        = str(grt.replyTo)
        return correlation_id, reply_to


    def _createReply(self, _, method, correlation_id):
        reply = self.decoder.marshal_result(correlation_id, method)
        return reply


    def _createFault(self, err, method):

        from xml.sax.saxutils import escape as xml_escape

        error_text = xml_escape( err.getErrorMessage() )

        log.msg('Error during service invocation: %s' % error_text)
        log.err(err)

        # need to do error type -> error id mapping
        reply = SERVICE_FAULT % {'error_id': 'N/A', 'error_text': error_text }
        return reply


    def queryServices(self, soap_action, soap_data):

        log.msg('', system='')
        print
        #print
        #print "Q NSA", soap_action
        assert soap_action == QUERY_SERVICES

        print "SD", soap_data

#        method, req = self.decoder.parse_request('queryNSA', soap_data)
#        print "REQ\n", req
#        request_type = req.requestType
#        print "RT", request_type
#        reply = self.decoder.marshal_result([], method)

        # check request type

        iso_now = datetime.datetime.utcnow().isoformat()
        iso_now = iso_now.rsplit('.',1)[0] + 'Z' # remove microseconds and add zulu designation

        services = [ { 'description' : 'hi there',
                       'versions'    :  [ { 'name' : 'NSI', 'version': '2', 'endpoint' : 'http://sager/ting' } ]
                     }
                   ]

        reply = soap.createQueryNSAResponsePayload('mynsaid', '1.2', iso_now, iso_now, services)

        print "REPLY\n", reply
        return reply

