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



LOG_SYSTEM = 'NSI2.ProviderService'



class ProviderService:

    def __init__(self, soap_resource, provider):

        self.provider = provider

        soap_resource.registerDecoder(actions.RESERVE,   self.reserve)
        soap_resource.registerDecoder(actions.PROVISION, self.provision)
        soap_resource.registerDecoder(actions.RELEASE,   self.release)
        soap_resource.registerDecoder(actions.TERMINATE, self.terminate)
        soap_resource.registerDecoder(actions.QUERY,     self.query)

        self.datetime_parser = parser.parser()

#       Actions we don't support yet.
#       The SOAPResource will respond with a 406 Not Acceptable, until they are added
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/modifyCheck"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/modify"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/modifyCancel"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/queryConfirmed"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/queryFailed"


    def _parseRequest(self, soap_data, rootClass=None):

        headers, bodies = minisoap.parseSoapPayload(soap_data)

        if headers is None:
            raise ValueError('No header specified in payload')
            #raise resource.SOAPFault('No header specified in payload')

        # more checking here...

        header = HT.parseString( ET.tostring( headers[0] ) )
        body   = CT.parseString( ET.tostring( bodies[0] ), rootClass=rootClass ) # only one body element supported for now

        return header, body


    def _createGenericAcknowledgement(self, _, correlation_id, requester_nsa, provider_nsa):

        header = HT.CommonHeaderType(None, correlation_id, requester_nsa, provider_nsa)
        header_payload = helper.export(header, 'acknowledgment')

        payload = minisoap.createSoapPayload(None, header_payload)
        return payload


    def _createSOAPFault(self, err, provider_nsa):

        if err.check(error.NSIError):
            variables = None
            se = CT.ServiceExceptionType(provider_nsa, err.value.errorId, err.getErrorMessage(), variables)
            detail = helper.export(se, 'serviceException', level=4)
        else:
            log.msg('Got a non NSIError exception, cannot create detailed fault (%s)' % type(err.value), system=LOG_SYSTEM)
            log.err(err)
            detail = None

        soap_fault = resource.SOAPFault( err.getErrorMessage(), detail )

        return failure.Failure(soap_fault)


    def reserve(self, soap_data):

        t_start = time.time()

        header, reservation = self._parseRequest(soap_data)

        # do some checking here

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

        src_stp = helper.createSTP(path.sourceSTP)
        dst_stp = helper.createSTP(path.destSTP)

        start_time = self.datetime_parser.parse(schedule.startTime)
        if start_time.utcoffset() is None:
            err = failure.Failure ( error.PayloadError('Start time has no time zone information') )
            return self._createSOAPFault(err, header.providerNSA)

        end_time   = self.datetime_parser.parse(schedule.endTime)
        if end_time.utcoffset() is None:
            err = failure.Failure ( error.PayloadError('End time has no time zone information') )
            return self._createSOAPFault(err, header.providerNSA)

        service_parameters = nsa.ServiceParameters(start_time, end_time, src_stp, dst_stp,
                                                  directionality=path.directionality, bandwidth=criteria.bandwidth)

        # change core classes in a way that nsi1 protocol can still handle it

        t_delta = time.time() - t_start
        log.msg('Profile: Reserve request parse time: %s' % round(t_delta, 3), profile=True, system=LOG_SYSTEM)

        d = self.provider.reserve(header.correlationId, header.replyTo, header.requesterNSA, header.providerNSA, session_security_attr,
                                  reservation.globalReservationId, reservation.description, reservation.connectionId, service_parameters)

        d.addCallbacks(self._createGenericAcknowledgement, self._createSOAPFault,
                       callbackArgs=(header.correlationId, header.requesterNSA, header.providerNSA),
                       errbackArgs=(header.providerNSA,))
        return d


    def provision(self, soap_data):

        header, generic_request = self._parseRequest(soap_data)

        session_security_attr = None

        d = self.provider.provision(header.correlationId, header.replyTo, header.requesterNSA, header.providerNSA, session_security_attr,
                                    generic_request.connectionId)

        d.addCallbacks(self._createGenericAcknowledgement, self._createSOAPFault,
                       callbackArgs=(header.correlationId, header.requesterNSA, header.providerNSA),
                       errbackArgs=(header.providerNSA,))
        return d


    def release(self, soap_data):

        header, generic_request = self._parseRequest(soap_data)

        session_security_attr = None

        d = self.provider.release(header.correlationId, header.replyTo, header.requesterNSA, header.providerNSA, session_security_attr,
                                  generic_request.connectionId)

        d.addCallbacks(self._createGenericAcknowledgement, self._createSOAPFault,
                       callbackArgs=(header.correlationId, header.requesterNSA, header.providerNSA),
                       errbackArgs=(header.providerNSA,))
        return d


    def terminate(self, soap_data):

        header, generic_request = self._parseRequest(soap_data)

        session_security_attr = None

        d = self.provider.terminate(header.correlationId, header.replyTo, header.requesterNSA, header.providerNSA, session_security_attr,
                                    generic_request.connectionId)

        d.addCallbacks(self._createGenericAcknowledgement, self._createSOAPFault,
                       callbackArgs=(header.correlationId, header.requesterNSA, header.providerNSA),
                       errbackArgs=(header.providerNSA,))
        return d


    def query(self, soap_data):

        #t_start = time.time()

        header, query = self._parseRequest(soap_data, CT.QueryType)

        session_security_attr = None
        filter_ = query.queryFilter

        d = self.provider.query(header.correlationId, header.replyTo, header.requesterNSA, header.providerNSA, session_security_attr,
                                query.operation, filter_.connectionId, filter_.globalReservationId)
        d.addCallbacks(self._createGenericAcknowledgement, self._createSOAPFault,
                       callbackArgs=(header.correlationId, header.requesterNSA, header.providerNSA),
                       errbackArgs=(header.providerNSA,))
        return d

