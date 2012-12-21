"""
Web Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from dateutil import parser
from xml.etree import cElementTree as ET

from twisted.python import log

from opennsa import nsa

from opennsa.protocols.shared import minisoap
from opennsa.protocols.nsi2 import actions, headertypes as HT, connectiontypes as CT, helper



LOG_SYSTEM = 'NSI2.RequesterService'



class RequesterService:

    def __init__(self, soap_resource, requester):

        self.requester = requester
        self.datetime_parser = parser.parser()

        # consider moving this to __init__ (soap_resource only used in setup)
        soap_resource.registerDecoder(actions.RESERVE_CONFIRMED,   self.reserveConfirmed)

        soap_resource.registerDecoder(actions.PROVISION_CONFIRMED, self.provisionConfirmed)

        soap_resource.registerDecoder(actions.RELEASE_CONFIRMED,   self.releaseConfirmed)

        soap_resource.registerDecoder(actions.TERMINATE_CONFIRMED, self.terminateConfirmed)

        soap_resource.registerDecoder(actions.QUERY_CONFIRMED,     self.queryConfirmed)

##        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/10/connection/service/reserveConfirmed"',      self.reserveConfirmed)
##        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/10/connection/service/reserveFailed"',         self.reserveFailed)
##
##        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/10/connection/service/provisionConfirmed"',    self.provisionConfirmed)
##        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/10/connection/service/provisionFailed"',       self.provisionFailed)
##
##        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/10/connection/service/releaseConfirmed"',      self.releaseConfirmed)
##        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/10/connection/service/releaseFailed"',         self.releaseFailed)
##
##        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/10/connection/service/terminateConfirmed"',    self.terminateConfirmed)
##        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/10/connection/service/terminateFailed"',       self.terminateFailed)
##
##        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/10/connection/service/queryConfirmed"',        self.queryConfirmed)
##        self.soap_resource.registerDecoder('"http://schemas.ogf.org/nsi/2011/10/connection/service/queryFailed"',           self.queryFailed)
##
##        #"http://schemas.ogf.org/nsi/2011/10/connection/service/forcedEnd"
##        #"http://schemas.ogf.org/nsi/2011/10/connection/service/query"


    def _parseGenericConfirm(self, soap_data):

        headers, bodies = minisoap.parseSoapPayload(soap_data)

        header = HT.parseString( ET.tostring( headers[0] ) )
        generic_confirm = CT.parseString( ET.tostring( bodies[0] ) )

        return header, generic_confirm


    def _createGenericAcknowledgement(self, correlation_id, requester_nsa, provider_nsa):

        header_payload = helper.createHeader(correlation_id, requester_nsa, provider_nsa)

        payload = minisoap.createSoapPayload(None, header_payload)
        return payload


    def reserveConfirmed(self, soap_data):

        headers, bodies = minisoap.parseSoapPayload(soap_data)

        header = HT.parseString( ET.tostring( headers[0] ) )
        reservation = CT.parseString( ET.tostring( bodies[0] ) )

        if type(reservation.criteria) == list and len(reservation.criteria) > 1:
            print "Multiple reservation criteria!"
            criteria = reservation.criteria[0]
        else:
            criteria = reservation.criteria

        schedule = criteria.schedule
        path = criteria.path

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

        self.requester.reserveConfirmed(header.correlationId, header.requesterNSA, header.providerNSA, session_security_attr,
                                        reservation.globalReservationId, reservation.description, reservation.connectionId, service_parameters)

        return self._createGenericAcknowledgement(header.correlationId, header.requesterNSA, header.providerNSA)


##    def reserveFailed(self, soap_data):
##
##        method, req = self.decoder.parse_request('reserveFailed', soap_data)
##
##        correlation_id = str(req.correlationId)
##        requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_id, error_message = self._getGFTParameters(req.reserveFailed)
##
##        self.requester.reserveFailed(correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_message)
##
##        reply = self.decoder.marshal_result(correlation_id, method)
##        return reply
##

    def provisionConfirmed(self, soap_data):

        header, generic_confirm = self._parseGenericConfirm(soap_data)

        session_security_attr = None

        self.requester.provisionConfirmed(header.correlationId, header.requesterNSA, header.providerNSA, session_security_attr,
                                          generic_confirm.connectionId)

        return self._createGenericAcknowledgement(header.correlationId, header.requesterNSA, header.providerNSA)


##    def provisionFailed(self, soap_data):
##
##        method, req = self.decoder.parse_request('provisionFailed', soap_data)
##
##        correlation_id = str(req.correlationId)
##        requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_id, error_message = self._getGFTParameters(req.provisionFailed)
##
##        d = self.requester.provisionFailed(correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_message)
##
##        reply = self.decoder.marshal_result(correlation_id, method)
##        return reply
##

    def releaseConfirmed(self, soap_data):

        header, generic_confirm = self._parseGenericConfirm(soap_data)

        session_security_attr = None

        self.requester.releaseConfirmed(header.correlationId, header.requesterNSA, header.providerNSA, session_security_attr,
                                        generic_confirm.connectionId)

        return self._createGenericAcknowledgement(header.correlationId, header.requesterNSA, header.providerNSA)


##    def releaseFailed(self, soap_data):
##
##        method, req = self.decoder.parse_request('releaseFailed', soap_data)
##
##        correlation_id = str(req.correlationId)
##        requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_id, error_message = self._getGFTParameters(req.releaseFailed)
##
##        d = self.requester.releaseFailed(correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_message)
##
##        reply = self.decoder.marshal_result(correlation_id, method)
##        return reply
##

    def terminateConfirmed(self, soap_data):

        header, generic_confirm = self._parseGenericConfirm(soap_data)

        session_security_attr = None

        self.requester.terminateConfirmed(header.correlationId, header.requesterNSA, header.providerNSA, session_security_attr,
                                          generic_confirm.connectionId)

        return self._createGenericAcknowledgement(header.correlationId, header.requesterNSA, header.providerNSA)


##    def terminateFailed(self, soap_data):
##
##        method, req = self.decoder.parse_request('terminateFailed', soap_data)
##
##        correlation_id = str(req.correlationId)
##        requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_id, error_message = self._getGFTParameters(req.terminateFailed)
##
##        d = self.requester.terminateFailed(correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_message)
##
##        reply = self.decoder.marshal_result(correlation_id, method)
##        return reply
##


    def queryConfirmed(self, soap_data):

        headers, bodies = minisoap.parseSoapPayload(soap_data)

        header          = HT.parseString( ET.tostring( headers[0] ) )
        query_confirmed = CT.parseString( ET.tostring( bodies[0]  ), rootClass=CT.QueryConfirmedType )

        query_result = query_confirmed.reservationSummary + query_confirmed.reservationDetails
        # should really do something more here...

        d = self.requester.queryConfirmed(header.correlationId, header.requesterNSA, header.providerNSA, query_result)

        return self._createGenericAcknowledgement(header.correlationId, header.requesterNSA, header.providerNSA)


##    def queryFailed(self, soap_data):
##
##        method, req = self.decoder.parse_request('queryFailed', soap_data)
##
##        correlation_id          = str(req.correlationId)
##
##        requester_nsa, provider_nsa = _decodeNSAs(req.queryFailed)
##
##        qf = req.queryFailed
##        #error_id                = str(qf.serviceException.messageId) if 'messageId' in qf.serviceException else None
##        error_message           = str(qf.serviceException.text)      if 'text' in qf.serviceException else None
##
##        d = self.requester.queryFailed(correlation_id, requester_nsa, provider_nsa, error_message)
##
##        reply = self.decoder.marshal_result(correlation_id, method)
##        return reply
##
