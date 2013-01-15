"""
Web Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import datetime
import StringIO
from twisted.python import log

from xml.etree import cElementTree as ET

from dateutil.tz import tzutc

from opennsa.protocols.shared import minisoap

from opennsa.protocols.discovery import soap, bindings as DT




LOG_SYSTEM = 'protocol.discover.service'

DISCOVERY_TYPES_NS = "http://schemas.ogf.org/nsi/2012/03/discovery/types"

QUERY_SERVICES = '"http://schemas.ogf.org/nsi/2012/03/discovery/service/queryServices"'



class DiscoverService:

    def __init__(self, soap_resource, discoverer):

        self.discoverer = discoverer

        soap_resource.registerDecoder(QUERY_SERVICES, self.queryServices)


    def queryServices(self, soap_data):

        log.msg('QUERY Services request', system=LOG_SYSTEM)
        log.msg("RECEIVED SOAP DATA\n\n" + soap_data, system=LOG_SYSTEM)

        headers, bodies = minisoap.parseSoapPayload(soap_data)

        qnr = DT.parseString( ET.tostring( bodies[0] ) )

        log.msg(qnr.requestType, system=LOG_SYSTEM)
        log.msg(qnr.filter, system=LOG_SYSTEM)

        log.msg("==", system=LOG_SYSTEM)

#        method, req = self.decoder.parse_request('queryNSA', soap_data)
#        print "REQ\n", req
#        request_type = req.requestType
#        print "RT", request_type
#        reply = self.decoder.marshal_result([], method)

        # check request type

        iso_now = datetime.datetime.now(tzutc()).isoformat()
        iso_now = iso_now.rsplit('.',1)[0] + 'Z' # remove microseconds and add zulu designation

        version = DT.VersionsType()

        service = DT.ServiceType()

        services = DT.ServicesType( [ service ] )

        discovery = DT.NsaDiscoveryType('opennsa-version', 'nsi-id', iso_now, iso_now, services)

        response = DT.QueryNsaResponseType(discovery)

        f = StringIO.StringIO()
        response.export(f, 0, namespacedef_='xmlns:tns="%s"' % DISCOVERY_TYPES_NS)
        payload = f.getvalue()
        log.msg("PAYLOAD\n\n" + payload, system=LOG_SYSTEM)
        log.msg("--", system=LOG_SYSTEM)

        services = [ { 'description' : 'hi there',
                       'versions'    :  [ { 'name' : 'NSI', 'version': '2', 'endpoint' : 'http://sager/ting' } ]
                     }
                   ]

        reply = soap.createQueryNSAResponsePayload('mynsaid', '1.2', iso_now, iso_now, services)

        print "REPLY\n", reply
        return reply

