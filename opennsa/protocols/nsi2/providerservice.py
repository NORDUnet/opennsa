"""
Web Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import time
from xml.etree import ElementTree as ET

from dateutil import parser
from dateutil.tz import tzutc

from twisted.python import log, failure

from opennsa import nsa, error
from opennsa.protocols.shared import minisoap, resource
from opennsa.protocols.nsi2 import actions, bindings, helper



LOG_SYSTEM = 'NSI2.ProviderService'



class ProviderService:

    def __init__(self, soap_resource, provider):

        self.provider = provider

        soap_resource.registerDecoder(actions.RESERVE,          self.reserve)
        soap_resource.registerDecoder(actions.RESERVE_COMMIT,   self.reserveCommit)
        soap_resource.registerDecoder(actions.RESERVE_ABORT,    self.reserveAbort)

        soap_resource.registerDecoder(actions.PROVISION,        self.provision)
        soap_resource.registerDecoder(actions.RELEASE,          self.release)
        soap_resource.registerDecoder(actions.TERMINATE,        self.terminate)

        soap_resource.registerDecoder(actions.QUERY_SUMMARY,     self.querySummary)

        self.datetime_parser = parser.parser()

#       Actions we don't support yet.
#       The SOAPResource will respond with a 406 Not Acceptable, until they are added
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/modifyCheck"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/modify"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/modifyCancel"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/queryConfirmed"
#        "http://schemas.ogf.org/nsi/2012/03/connection/service/queryFailed"


    def _createGenericAcknowledgement(self, _, nsi_header):

        soap_header = bindings.CommonHeaderType(helper.PROTO, nsi_header.correlation_id, nsi_header.requester_nsa, nsi_header.provider_nsa, None, nsi_header.session_security_attrs)
        soap_header_element = soap_header.xml(bindings.acknowledgment)
        payload = minisoap.createSoapPayload(None, soap_header_element)
        return payload


    def _createSOAPFault(self, err, provider_nsa, connection_id=None):

        se = helper.createServiceException(err, provider_nsa, connection_id)
        element = se.xml(bindings.serviceException)
        detail = ET.tostring(element)

        soap_fault = resource.SOAPFault( err.getErrorMessage(), detail )

        return failure.Failure(soap_fault)


    def reserve(self, soap_data):

        t_start = time.time()

        header, reservation = helper.parseRequest(soap_data)

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

        # convert to utc and remove timezone
        start_time = start_time.astimezone(tzutc()).replace(tzinfo=None)
        end_time   = end_time.astimezone(tzutc()).replace(tzinfo=None)

        service_parameters = nsa.ServiceParameters(start_time, end_time, src_stp, dst_stp, directionality=path.directionality, bandwidth=criteria.bandwidth)

        t_delta = time.time() - t_start
        log.msg('Profile: Reserve request parse time: %s' % round(t_delta, 3), profile=True, system=LOG_SYSTEM)

        d = self.provider.reserve(header, reservation.connectionId, reservation.globalReservationId, reservation.description, service_parameters)

        d.addCallbacks(self._createGenericAcknowledgement, self._createSOAPFault, callbackArgs=(header,), errbackArgs=(header.provider_nsa,))
        return d



    def reserveCommit(self, soap_data):
        header, request = helper.parseRequest(soap_data)
        d = self.provider.reserveCommit(header, request.connectionId)
        d.addCallbacks(self._createGenericAcknowledgement, self._createSOAPFault, callbackArgs=(header,), errbackArgs=(header.provider_nsa, request.connectionId))
        return d


    def reserveAbort(self, soap_data):
        header, request = helper.parseRequest(soap_data)
        session_security_attr = None
        d = self.provider.reserveAbort(header.correlationId, header.replyTo, header.requesterNSA, header.providerNSA, session_security_attr,
                                       request.connectionId)
        d.addCallbacks(self._createGenericAcknowledgement, self._createSOAPFault, callbackArgs=(header,), errbackArgs=(header.provider_nsa, request.connectionId))
        return d


    def provision(self, soap_data):
        header, request = helper.parseRequest(soap_data)
        d = self.provider.provision(header, request.connectionId)
        d.addCallbacks(self._createGenericAcknowledgement, self._createSOAPFault, callbackArgs=(header,), errbackArgs=(header.provider_nsa, request.connectionId))
        return d


    def release(self, soap_data):
        header, request = helper.parseRequest(soap_data)
        d = self.provider.release(header, request.connectionId)
        d.addCallbacks(self._createGenericAcknowledgement, self._createSOAPFault, callbackArgs=(header,), errbackArgs=(header.provider_nsa, request.connectionId))
        return d


    def terminate(self, soap_data):

        header, request = helper.parseRequest(soap_data)
        d = self.provider.terminate(header, request.connectionId)

        d.addCallbacks(self._createGenericAcknowledgement, self._createSOAPFault, callbackArgs=(header,), errbackArgs=(header.provider_nsa, request.connectionId))
        return d


    def querySummary(self, soap_data):

        header, query = helper.parseRequest(soap_data, bindings.QueryType)

        session_security_attr = None
        filter_ = query.queryFilter

        d = self.provider.query(header.correlationId, header.replyTo, header.requesterNSA, header.providerNSA, session_security_attr,
                                query.operation, filter_.connectionId, filter_.globalReservationId)
        d.addCallbacks(self._createGenericAcknowledgement, self._createSOAPFault,
                       callbackArgs=(header.correlationId, header.requesterNSA, header.providerNSA), errbackArgs=(header.provider_nsa,))
        return d

