"""
Web Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from opennsa import nsa
from opennsa.shared import xmlhelper
from opennsa.protocols.nsi2 import helper, queryhelper
from opennsa.protocols.nsi2.bindings import actions, p2pservices


LOG_SYSTEM = 'RequesterService'



class RequesterService:

    def __init__(self, soap_resource, requester):

        self.requester = requester

        # consider moving this to __init__ (soap_resource only used in setup)
        soap_resource.registerDecoder(actions.RESERVE_CONFIRMED,        self.reserveConfirmed)
        soap_resource.registerDecoder(actions.RESERVE_FAILED,           self.reserveFailed)
        soap_resource.registerDecoder(actions.RESERVE_COMMIT_CONFIRMED, self.reserveCommitConfirmed)
        soap_resource.registerDecoder(actions.RESERVE_COMMIT_FAILED,    self.reserveCommitFailed)
        soap_resource.registerDecoder(actions.RESERVE_ABORT_CONFIRMED,  self.reserveAbortConfirmed)

        soap_resource.registerDecoder(actions.PROVISION_CONFIRMED,      self.provisionConfirmed)
        soap_resource.registerDecoder(actions.RELEASE_CONFIRMED,        self.releaseConfirmed)
        soap_resource.registerDecoder(actions.TERMINATE_CONFIRMED,      self.terminateConfirmed)

        soap_resource.registerDecoder(actions.QUERY_SUMMARY_CONFIRMED,  self.querySummaryConfirmed)
        soap_resource.registerDecoder(actions.QUERY_RECURSIVE_CONFIRMED,self.queryRecursiveConfirmed)

#        actions.QUERY_RECURSIVE_CONFIRMED
#        actions.QUERY_RECURSIVE_FAILED
#        actions.QUERY_NOTIFICATION_CONFIRMED
#        actions.QUERY_NOTIFICATION_FAILED

        # notifications
        soap_resource.registerDecoder(actions.ERROR,                    self.error)
        soap_resource.registerDecoder(actions.ERROR_EVENT,              self.errorEvent)
        soap_resource.registerDecoder(actions.DATA_PLANE_STATE_CHANGE,  self.dataPlaneStateChange)
        soap_resource.registerDecoder(actions.RESERVE_TIMEOUT,          self.reserveTimeout)
        soap_resource.registerDecoder(actions.MESSAGE_DELIVERY_TIMEOUT, self.messageDeliveryTimeout)


    def _parseGenericFailure(self, soap_data):

        header, generic_failure = helper.parseRequest(soap_data)

        rc = generic_failure.connectionStates
        rd = rc.dataPlaneStatus

        dps = (rd.active, rd.version, rd.versionConsistent)
        cs = (rc.reservationState, rc.provisionState, rc.lifecycleState, dps)

        ex = helper.createException(generic_failure.serviceException, header.provider_nsa)
        return header, generic_failure.connectionId, cs, ex


    def reserveConfirmed(self, soap_data, request_info):

        header, reservation = helper.parseRequest(soap_data)

        criteria = reservation.criteria

        # Create DTOs - this overlaps heavily with the parsing done in providerservice - unify sometime

        start_time = xmlhelper.parseXMLTimestamp(criteria.schedule.startTime) if criteria.schedule.startTime is not None else None
        end_time   = xmlhelper.parseXMLTimestamp(criteria.schedule.endTime)   if criteria.schedule.endTime   is not None else None
        schedule   = nsa.Schedule(start_time, end_time)

        # check for service type sometime
        p2ps = criteria.serviceDefinition
        if type(p2ps) is not p2pservices.P2PServiceBaseType:
            raise ValueError('Only P2P service supported.')

        # (ERO missing)
        src_stp = helper.createSTP(p2ps.sourceSTP)
        dst_stp = helper.createSTP(p2ps.destSTP)

        if p2ps.ero:
            print "ERO parsing in reserveConfirmed not implemented yet, full path will not be available"

        sd = nsa.Point2PointService(src_stp, dst_stp, p2ps.capacity, p2ps.directionality, p2ps.symmetricPath, None)
        crt = nsa.Criteria(criteria.version, schedule, sd)

        self.requester.reserveConfirmed(header, reservation.connectionId,  reservation.globalReservationId, reservation.description, crt)

        return helper.createGenericRequesterAcknowledgement(header)


    def reserveFailed(self, soap_data, request_info):
        header, connection_id, cs, err = self._parseGenericFailure(soap_data)
        self.requester.reserveFailed(header, connection_id, cs, err)
        return helper.createGenericRequesterAcknowledgement(header)


    def reserveCommitConfirmed(self, soap_data, request_info):
        header, generic_confirm = helper.parseRequest(soap_data)
        self.requester.reserveCommitConfirmed(header, generic_confirm.connectionId)
        return helper.createGenericRequesterAcknowledgement(header)


    def reserveCommitFailed(self, soap_data, request_info):
        header, connection_id, cs, err = self._parseGenericFailure(soap_data)
        self.requester.reserveCommitFailed(header, connection_id, cs, err)
        return helper.createGenericRequesterAcknowledgement(header)


    def reserveAbortConfirmed(self, soap_data, request_info):
        header, generic_confirm = helper.parseRequest(soap_data)
        self.requester.reserveAbortConfirmed(header, generic_confirm.connectionId)
        return helper.createGenericRequesterAcknowledgement(header)


    def provisionConfirmed(self, soap_data, request_info):
        header, generic_confirm = helper.parseRequest(soap_data)
        self.requester.provisionConfirmed(header, generic_confirm.connectionId)
        return helper.createGenericRequesterAcknowledgement(header)


    def releaseConfirmed(self, soap_data, request_info):
        header, generic_confirm = helper.parseRequest(soap_data)
        self.requester.releaseConfirmed(header, generic_confirm.connectionId)
        return helper.createGenericRequesterAcknowledgement(header)


    def terminateConfirmed(self, soap_data, request_info):
        header, generic_confirm = helper.parseRequest(soap_data)
        self.requester.terminateConfirmed(header, generic_confirm.connectionId)
        return helper.createGenericRequesterAcknowledgement(header)


    def terminateFailed(self, soap_data, request_info):
        header, connection_id, cs, err = self._parseGenericFailure(soap_data)
        self.requester.terminateFailed(header, connection_id, cs, err)
        return helper.createGenericRequesterAcknowledgement(header)


    def querySummaryConfirmed(self, soap_data, request_info):

        header, query_result = helper.parseRequest(soap_data)

        reservations = [ queryhelper.buildQueryResult(res, header.provider_nsa) for res in query_result.reservations ]

        self.requester.querySummaryConfirmed(header, reservations)

        return helper.createGenericRequesterAcknowledgement(header)


    def queryRecursiveConfirmed(self, soap_data, request_info):

        header, query_result = helper.parseRequest(soap_data)

        reservations = [ queryhelper.buildQueryResult(res, header.provider_nsa, include_children=True) for res in query_result.reservations ]

        self.requester.queryRecursiveConfirmed(header, reservations)

        return helper.createGenericRequesterAcknowledgement(header)


    def error(self, soap_data, request_info):

        header, error = helper.parseRequest(soap_data)
        se = error.serviceException
        # service exception fields, we are not quite there yet...
        # nsaId  # NsaIdType -> anyURI
        # connectionId  # ConnectionIdType -> string
        # serviceType  # string
        # errorId  # string
        # text  # string
        # variables  # [ TypeValuePairType ]
        # childException  # [ ServiceException ]
        variables = [ (tvp.type, tvp.value) for tvp in se.variables ]
        child_ex = None

        self.requester.error(header, se.nsaId, se.connectionId, se.serviceType, se.errorId, se.text, variables, child_ex)

        return helper.createGenericRequesterAcknowledgement(header)


    def errorEvent(self, soap_data, request_info):

        header, error_event = helper.parseRequest(soap_data)

        #connection_id, notification_id, timestamp, event, info, service_ex = 
        ee = error_event
        if ee.serviceException:
            se = ee.serviceException
            service_ex = (se.nsaId, se.connectionId, se.errorId, se.text, se.variables, se.childException)
        else:
            service_ex = None

        self.requester.errorEvent(header, ee.connectionId, ee.notificationId, ee.timeStamp, ee.event, ee.additionalInfo, service_ex)

        return helper.createGenericRequesterAcknowledgement(header)



    def dataPlaneStateChange(self, soap_data, request_info):

        header, data_plane_state_change = helper.parseRequest(soap_data)

        dpsc = data_plane_state_change
        dps = dpsc.dataPlaneStatus

        self.requester.dataPlaneStateChange(header, dpsc.connectionId, dpsc.notificationId, dpsc.timeStamp, (dps.active, dps.version, dps.versionConsistent) )

        return helper.createGenericRequesterAcknowledgement(header)


    def reserveTimeout(self, soap_data, request_info):

        header, reserve_timeout = helper.parseRequest(soap_data)

        rt = reserve_timeout
        timestamp = xmlhelper.parseXMLTimestamp(rt.timeStamp)
        self.requester.reserveTimeout(header, rt.connectionId, rt.notificationId, timestamp, rt.timeoutValue, rt.originatingConnectionId, rt.originatingNSA)

        return helper.createGenericRequesterAcknowledgement(header)


    def messageDeliveryTimeout(self, soap_data, request_info):
        raise NotImplementedError('messageDeliveryTimeout not yet implemented in requester service')

