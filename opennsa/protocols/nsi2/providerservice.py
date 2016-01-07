"""
Web Service Resource for OpenNSA.

This module turns soap data into usefull data structures.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2015)
"""

import time

from twisted.python import log, failure

from opennsa import nsa, error
from opennsa.shared import xmlhelper
from opennsa.protocols.shared import minisoap, soapresource
from opennsa.protocols.nsi2 import helper, queryhelper
from opennsa.protocols.nsi2.bindings import actions, nsiconnection, p2pservices



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
        soap_resource.registerDecoder(actions.QUERY_SUMMARY_SYNC,self.querySummarySync)
        soap_resource.registerDecoder(actions.QUERY_RECURSIVE,   self.queryRecursive)

        # Some actions still missing


    def _createSOAPFault(self, err, provider_nsa, connection_id=None, service_type=None):

        log.msg('Request error: %s. Returning error to remote client.' % err.getErrorMessage(), system=LOG_SYSTEM)

        se = helper.createServiceException(err, provider_nsa, connection_id)
        ex_element = se.xml(nsiconnection.serviceException)

        soap_fault = soapresource.SOAPFault( err.getErrorMessage(), ex_element )
        return soap_fault


    def reserve(self, soap_data, request_info):

        t_start = time.time()

        header, reservation = helper.parseRequest(soap_data)

        # do some checking here

#        print header.protocolVersion
#        print header.correlationId
#        print header.requesterNSA
#        print header.providerNSA
#        print header.replyTo

        criteria = reservation.criteria

        #version      = criteria.version # not used at the moment
        service_type = criteria.serviceType # right now we just ignore this, either we know the service type or not
        p2ps         = criteria.serviceDefinition

#        if len(service_defs) == 0:
#            err = failure.Failure ( error.PayloadError('No service definition element in message') )
#            return self._createSOAPFault(err, header.provider_nsa, service_type=service_type)

#        if len(service_defs) != 1:
#            err = failure.Failure ( error.PayloadError('Only one service definition allowed') )
#            return self._createSOAPFault(err, header.provider_nsa, service_type=service_type)

        if type(p2ps) is not p2pservices.P2PServiceBaseType:
            err = failure.Failure ( error.PayloadError('Only supports Point2PointService service for now.') )
            return self._createSOAPFault(err, header.provider_nsa, service_type=service_type)

        if p2ps.directionality in (None, ''):
            err = failure.Failure ( error.MissingParameterError('Directionality parameter not defined'))
            return self._createSOAPFault(err, header.provider_nsa)

        # create DTOs (EROs not supported yet)

        start_time = xmlhelper.parseXMLTimestamp(criteria.schedule.startTime) if criteria.schedule.startTime is not None else None
        end_time = xmlhelper.parseXMLTimestamp(criteria.schedule.endTime) if criteria.schedule.endTime is not None else None
        schedule = nsa.Schedule(start_time, end_time)

        src_stp = helper.createSTP(p2ps.sourceSTP)
        dst_stp = helper.createSTP(p2ps.destSTP)

        if p2ps.ero:
            err = failure.Failure ( error.PayloadError('ERO not supported, go away.') )
            return self._createSOAPFault(err, header.provider_nsa)

#        if p2ps.parameter:
#            p = p2ps.parameter[0]
#            err = failure.Failure ( error.UnsupportedParameter('Unsupported parameter: %s/%s' % (p.type_, p.value) ) )
#            return self._createSOAPFault(err, header.provider_nsa)
        params = [ (p.type_, p.value) for p in p2ps.parameter ] if p2ps.parameter else None
        symmetric = p2ps.symmetricPath or False # the p2p service specifies default behaviour as false, but doesn't specify default
        sd = nsa.Point2PointService(src_stp, dst_stp, p2ps.capacity, p2ps.directionality, symmetric, None, params)

        crt = nsa.Criteria(criteria.version, schedule, sd)

        t_delta = time.time() - t_start
        log.msg('Profile: Reserve request parse time: %s' % round(t_delta, 3), profile=True, system=LOG_SYSTEM)

        d = self.provider.reserve(header, reservation.connectionId, reservation.globalReservationId, reservation.description, crt, request_info)

        def createReserveAcknowledgement(connection_id):
            # no reply to / security attrs / trace
            soap_header_element = helper.createProviderHeader(header.requester_nsa, header.provider_nsa, None, header.correlation_id)

            reserve_response = nsiconnection.ReserveResponseType(connection_id)
            reserve_response_element = reserve_response.xml(nsiconnection.reserveResponse)

            payload = minisoap.createSoapPayload(reserve_response_element, soap_header_element)
            return payload


        d.addCallbacks(createReserveAcknowledgement, self._createSOAPFault, errbackArgs=(header.provider_nsa,))
        return d



    def reserveCommit(self, soap_data, request_info):
        header, confirm = helper.parseRequest(soap_data)
        d = self.provider.reserveCommit(header, confirm.connectionId, request_info)
        d.addCallbacks(lambda _ : helper.createGenericProviderAcknowledgement(header), self._createSOAPFault, errbackArgs=(header.provider_nsa, confirm.connectionId))
        return d


    def reserveAbort(self, soap_data, request_info):
        header, request = helper.parseRequest(soap_data)
        d = self.provider.reserveAbort(header, request.connectionId, request_info)
        d.addCallbacks(lambda _ : helper.createGenericProviderAcknowledgement(header), self._createSOAPFault, errbackArgs=(header.provider_nsa, request.connectionId))
        return d


    def provision(self, soap_data, request_info):
        header, request = helper.parseRequest(soap_data)
        d = self.provider.provision(header, request.connectionId, request_info)
        d.addCallbacks(lambda _ : helper.createGenericProviderAcknowledgement(header), self._createSOAPFault, errbackArgs=(header.provider_nsa, request.connectionId))
        return d


    def release(self, soap_data, request_info):
        header, request = helper.parseRequest(soap_data)
        d = self.provider.release(header, request.connectionId, request_info)
        d.addCallbacks(lambda _ : helper.createGenericProviderAcknowledgement(header), self._createSOAPFault, errbackArgs=(header.provider_nsa, request.connectionId))
        return d


    def terminate(self, soap_data, request_info):

        header, request = helper.parseRequest(soap_data)
        d = self.provider.terminate(header, request.connectionId, request_info)
        d.addCallbacks(lambda _ : helper.createGenericProviderAcknowledgement(header), self._createSOAPFault, errbackArgs=(header.provider_nsa, request.connectionId))
        return d


    def querySummary(self, soap_data, request_info):

        header, query = helper.parseRequest(soap_data)
        d = self.provider.querySummary(header, query.connectionId, query.globalReservationId, request_info)
        d.addCallbacks(lambda _ : helper.createGenericProviderAcknowledgement(header), self._createSOAPFault, errbackArgs=(header.provider_nsa,))
        return d


    def querySummarySync(self, soap_data, request_info):

        def gotReservations(reservations, header):
            # do reply inline
            soap_header_element = helper.createProviderHeader(header.requester_nsa, header.provider_nsa, correlation_id=header.correlation_id)

            qs_reservations = queryhelper.buildQuerySummaryResultType(reservations)

            qsct = nsiconnection.QuerySummaryConfirmedType(qs_reservations)

            payload = minisoap.createSoapPayload(qsct.xml(nsiconnection.querySummarySyncConfirmed), soap_header_element)
            return payload

        header, query = helper.parseRequest(soap_data)
        d = self.provider.querySummarySync(header, query.connectionId, query.globalReservationId, request_info)
        d.addCallbacks(gotReservations, self._createSOAPFault, callbackArgs=(header,), errbackArgs=(header.provider_nsa,))
        return d


    def queryRecursive(self, soap_data, request_info):

        header, query = helper.parseRequest(soap_data)
        d = self.provider.queryRecursive(header, query.connectionId, query.globalReservationId, request_info)
        d.addCallbacks(lambda _ : helper.createGenericProviderAcknowledgement(header), self._createSOAPFault, errbackArgs=(header.provider_nsa,))
        return d

