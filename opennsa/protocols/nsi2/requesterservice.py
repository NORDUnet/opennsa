"""
Web Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from dateutil import parser

from twisted.python import log

from opennsa import nsa, error

from opennsa.protocols.shared import minisoap
from opennsa.protocols.nsi2 import actions, bindings, helper



LOG_SYSTEM = 'NSI2.RequesterService'



class RequesterService:

    def __init__(self, soap_resource, requester):

        self.requester = requester
        self.datetime_parser = parser.parser()

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
        soap_resource.registerDecoder(actions.QUERY_SUMMARY_FAILED,     self.querySummaryFailed)

#        actions.QUERY_RECURSIVE_CONFIRMED
#        actions.QUERY_RECURSIVE_FAILED
#        actions.QUERY_NOTIFICATION_CONFIRMED
#        actions.QUERY_NOTIFICATION_FAILED

        # notifications
        soap_resource.registerDecoder(actions.ERROR_EVENT,              self.errorEvent)
        soap_resource.registerDecoder(actions.DATA_PLANE_STATE_CHANGE,  self.dataPlaneStateChange)
        soap_resource.registerDecoder(actions.RESERVE_TIMEOUT,          self.reserveTimeout)
        soap_resource.registerDecoder(actions.MESSAGE_DELIVERY_TIMEOUT, self.messageDeliveryTimeout)


    def _parseGenericFailure(self, soap_data):

        header, generic_failure = helper.parseRequest(soap_data)

        service_exception = generic_failure.serviceException

        exception_type = error.lookup(service_exception.errorId)
        err = exception_type(service_exception.text)

        return header, generic_failure, err



    def reserveConfirmed(self, soap_data):

        header, reservation = helper.parseRequest(soap_data)

        if len(reservation.criteria) > 1:
            print "Multiple reservation criteria!"

        criteria = reservation.criteria[0]

        schedule = criteria.schedule
        path = criteria.path

        # create DTOs

        # Missing: EROs, symmetric, stp labels

        ss = path.sourceSTP
        ds = path.destSTP

        source_stp = nsa.STP(ss.networkId, ss.localId)
        dest_stp   = nsa.STP(ds.networkId, ds.localId)

        start_time = self.datetime_parser.parse(schedule.startTime)
        end_time   = self.datetime_parser.parse(schedule.endTime)

        service_parameters = nsa.ServiceParameters(start_time, end_time, source_stp, dest_stp, directionality=path.directionality, bandwidth=criteria.bandwidth)

        self.requester.reserveConfirmed(header, reservation.connectionId,  reservation.globalReservationId, reservation.description, service_parameters)

        return helper.createGenericAcknowledgement(header)


    def reserveFailed(self, soap_data):
        header, generic_failure, err = self._parseGenericFailure(soap_data)
        self.requester.reserveFailed(header, generic_failure.connectionId, err)
        return helper.createGenericAcknowledgement(header)


    def reserveCommitConfirmed(self, soap_data):
        header, generic_confirm = helper.parseRequest(soap_data)
        self.requester.reserveCommitConfirmed(header, generic_confirm.connectionId)
        return helper.createGenericAcknowledgement(header)


    def reserveCommitFailed(self, soap_data):
        header, generic_failure, err = self._parseGenericFailure(soap_data)
        self.requester.reserveCommitFailed(header, generic_failure.connectionId, err)
        return helper.createGenericAcknowledgement(header)


    def reserveAbortConfirmed(self, soap_data):
        header, generic_confirm = helper.parseRequest(soap_data)
        self.requester.reserveAbortConfirmed(header, generic_confirm.connectionId)
        return helper.createGenericAcknowledgement(header)


    def provisionConfirmed(self, soap_data):
        header, generic_confirm = helper.parseRequest(soap_data)
        self.requester.provisionConfirmed(header, generic_confirm.connectionId)
        return helper.createGenericAcknowledgement(header)


    def releaseConfirmed(self, soap_data):
        header, generic_confirm = helper.parseRequest(soap_data)
        self.requester.releaseConfirmed(header, generic_confirm.connectionId)
        return helper.createGenericAcknowledgement(header)


    def terminateConfirmed(self, soap_data):
        header, generic_confirm = helper.parseRequest(soap_data)
        self.requester.terminateConfirmed(header, generic_confirm.connectionId)
        return helper.createGenericAcknowledgement(header)


    def terminateFailed(self, soap_data):

        header, generic_failure, err = self._parseGenericFailure(soap_data)
        session_security_attr = None

        self.requester.terminateFailed(header.correlationId, header.requesterNSA, header.providerNSA, session_security_attr,
                                       generic_failure.connectionId, err)

        return helper.createGenericAcknowledgement(header)


    def querySummaryConfirmed(self, soap_data):

        header, query_confirmed = minisoap.parseSoapPayload(soap_data)

#        header          = bindings.parseString( ET.tostring( headers[0] ) )
#        query_confirmed = bindings.parseString( ET.tostring( bodies[0]  ) )

        query_result = query_confirmed.reservationSummary + query_confirmed.reservationDetails
        # should really do something more here...

        d = self.requester.queryConfirmed(header, query_result)

        return helper.createGenericAcknowledgement(header)


    def querySummaryFailed(self, soap_data):

        header, generic_failure, err = self._parseGenericFailure(soap_data)
        session_security_attr = None

        self.requester.queryFailed(header.correlationId, header.requesterNSA, header.providerNSA, session_security_attr,
                                       generic_failure.connectionId, err)

        return helper.createGenericAcknowledgement(header)


    def errorEvent(self, soap_data):

        header, error_event = helper.parseRequest(soap_data)

        #connection_id, notification_id, timestamp, event, info, service_ex = 
        ee = error_event
        if ee.serviceException:
            se = ee.serviceException
            service_ex = (se.nsaId, se.connectionId, se.errorId, se.text, se.variables, se.childException)
        else:
            service_ex = None

        self.requester.errorEvent(header, ee.connectionId, ee.notificationId, ee.timeStamp, ee.event, ee.additionalInfo, service_ex)

        return helper.createGenericAcknowledgement(header)



    def dataPlaneStateChange(self, soap_data):

        header, data_plane_state_change = helper.parseRequest(soap_data)

        dpsc = data_plane_state_change
        dps = dpsc.dataPlaneStatus

        self.requester.dataPlaneStateChange(header, dpsc.connectionId, dpsc.notificationId, dpsc.timeStamp, (dps.active, dps.version, dps.versionConsistent) )

        return helper.createGenericAcknowledgement(header)


    def reserveTimeout(self, soap_data):
        raise NotImplementedError('reserveTimeout not yet implemented in requester service')


    def messageDeliveryTimeout(self, soap_data):
        raise NotImplementedError('messageDeliveryTimeout not yet implemented in requester service')

