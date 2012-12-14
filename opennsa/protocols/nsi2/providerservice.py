"""
Web Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import time
import StringIO
from xml.etree import cElementTree as ET

from dateutil import parser

from twisted.python import log, failure

from opennsa import nsa, error
from opennsa.protocols.shared import minisoap, resource
from opennsa.protocols.nsi2 import actions, connectiontypes as CT, headertypes as HT, helper



LOG_SYSTEM = 'protocols.CS2.ProviderService'



class ProviderService:

    def __init__(self, soap_resource, provider):

        self.provider = provider

        soap_resource.registerDecoder(actions.RESERVE,   self.reserve)
        soap_resource.registerDecoder(actions.PROVISION, self.provision)
        soap_resource.registerDecoder(actions.RELEASE,   self.release)
        soap_resource.registerDecoder(actions.TERMINATE, self.terminate)
#        soap_resource.registerDecoder(actions.QUERY,     self.query)

        self.datetime_parser = parser.parser()

#        "http://schemas.ogf.org/nsi/2012/03/connection/service/reserve"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/modifyCheck"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/modify"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/modifyCancel"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/provision"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/release"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/terminate"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/query"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/queryConfirmed"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/queryFailed"


    def _parseGenericRequest(self, soap_data):

        headers, bodies = minisoap.parseSoapPayload(soap_data)

        # do some checking here

        header = HT.parseString( ET.tostring( headers[0] ) )
        generic_request = CT.parseString( ET.tostring( bodies[0] ) )

        return header, generic_request


    def _createGenericAcknowledgement(self, _, correlation_id, requester_nsa, provider_nsa):

        header = HT.CommonHeaderType(None, correlation_id, requester_nsa, provider_nsa)
        header_payload = helper.export(header, helper.FRAMEWORK_TYPES_NS, 'acknowledgment')

        payload = minisoap.createSoapPayload(None, header_payload)
        return payload


    def _createSOAPFault(self, err, provider_nsa):

        if err.check(error.NSIError):
            variables = None
            se = CT.ServiceExceptionType(provider_nsa, err.value.errorId, err.getErrorMessage(), variables)
            detail = helper.export(se, helper.FRAMEWORK_TYPES_NS)
            print "FAULT DETAIL", detail
        else:
            log.msg('Got a non NSIError exception, cannot create detailed fault (%s)' % type(err.value), system=LOG_SYSTEM)
            detail = None

        soap_fault = resource.SOAPFault( err.getErrorMessage(), detail )

        return failure.Failure(soap_fault)


    def reserve(self, soap_data):

        t_start = time.time()

        headers, bodies = minisoap.parseSoapPayload(soap_data)

        # do some checking here

        header = HT.parseString( ET.tostring( headers[0] ) )
        reservation = CT.parseString( ET.tostring( bodies[0] ) )

        print "--"

#        print header.protocolVersion
#        print header.correlationId
#        print header.requesterNSA
#        print header.providerNSA
#        print header.replyTo

        criteria = reservation.criteria
        schedule = criteria.schedule
        path = criteria.path

#        print reservation.globalReservationId
#        print reservation.description
#        print reservation.connectionId
#        print reservation.criteria
#
#        print criteria.bandwidth
#        print criteria.path
#
#        print schedule.startTime
#        print schedule.endTime
#
#        print path.directionality
#        print path.sourceSTP
#        print path.destSTP

        # create DTOs

        # Missing: EROs, symmetric, stp labels

        session_security_attr = None

        ss = path.sourceSTP
        ds = path.destSTP

        source_stp = nsa.STP(ss.networkId, ss.localId)
        dest_stp   = nsa.STP(ds.networkId, ds.localId)

        start_time = self.datetime_parser.parse(schedule.startTime)
        end_time   = self.datetime_parser.parse(schedule.endTime)

        service_parameters = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp,
                                                  directionality=path.directionality, bandwidth=criteria.bandwidth)

        # change core classes in a way that nsi1 protocol can still handle it

        t_delta = time.time() - t_start
        log.msg('Profile: Reserve2 request parse time: %s' % round(t_delta, 3), profile=True, system=LOG_SYSTEM)

        d = self.provider.reserve(header.correlationId, header.replyTo, header.requesterNSA, header.providerNSA, session_security_attr,
                                  reservation.globalReservationId, reservation.description, reservation.connectionId, service_parameters)

        d.addCallbacks(self._createGenericAcknowledgement, self._createSOAPFault,
                       callbackArgs=(header.correlationId, header.requesterNSA, header.providerNSA),
                       errbackArgs=(header.providerNSA,))
        return d


    def provision(self, soap_data):

        header, generic_request = self._parseGenericRequest(soap_data)

        session_security_attr = None

        d = self.provider.provision(header.correlationId, header.replyTo, header.requesterNSA, header.providerNSA, session_security_attr,
                                    generic_request.connectionId)

        d.addCallbacks(self._createGenericAcknowledgement, self._createSOAPFault,
                       callbackArgs=(header.correlationId, header.requesterNSA, header.providerNSA),
                       errbackArgs=(header.providerNSA,))
        return d


    def release(self, soap_data):

        header, generic_request = self._parseGenericRequest(soap_data)

        session_security_attr = None

        d = self.provider.release(header.correlationId, header.replyTo, header.requesterNSA, header.providerNSA, session_security_attr,
                                  generic_request.connectionId)

        d.addCallbacks(self._createGenericAcknowledgement, self._createSOAPFault,
                       callbackArgs=(header.correlationId, header.requesterNSA, header.providerNSA),
                       errbackArgs=(header.providerNSA,))
        return d


    def terminate(self, soap_data):

        header, generic_request = self._parseGenericRequest(soap_data)

        session_security_attr = None

        d = self.provider.terminate(header.correlationId, header.replyTo, header.requesterNSA, header.providerNSA, session_security_attr,
                                    generic_request.connectionId)

        d.addCallbacks(self._createGenericAcknowledgement, self._createSOAPFault,
                       callbackArgs=(header.correlationId, header.requesterNSA, header.providerNSA),
                       errbackArgs=(header.providerNSA,))
        return d

#
#    def query(self, soap_data):
#
#        method, req = self.decoder.parse_request('query', soap_data)
#
#        requester_nsa, provider_nsa = _decodeNSAs(req.query)
#        correlation_id = str(req.correlationId)
#        reply_to       = str(req.replyTo)
#
#        operation = req.query.operation
#        qf = req.query.queryFilter
#
#        connection_ids = None
#        global_reservation_ids = None
#
#        if 'connectionId' in qf:
#            connection_ids = qf.connectionId
#        if 'globalReservationId' in qf:
#            global_reservation_ids = qf.globalReservationId
#
#        d = self.provider.query(correlation_id, reply_to, requester_nsa, provider_nsa, None, operation, connection_ids, global_reservation_ids)
#        d.addCallbacks(self._createReply, self._createSOAPFault, callbackArgs=(method,correlation_id), errbackArgs=(method,))
#        return d
#
