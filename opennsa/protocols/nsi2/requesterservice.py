"""
Web Service Resource for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import time
import StringIO
from dateutil import parser
from xml.etree import cElementTree as ET

from twisted.python import log

from opennsa import nsa

from opennsa.protocols.shared import minisoap
from opennsa.protocols.nsi2 import actions, headertypes as HT, connectiontypes as CT



LOG_SYSTEM = 'protocol.nsi2.RequesterService'

FRAMEWORK_TYPES_NS  = "http://schemas.ogf.org/nsi/2012/03/framework/types"


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



##def _decodeNSAs(subreq):
##    requester_nsa = str(subreq.requesterNSA)
##    provider_nsa  = str(subreq.providerNSA)
##    return requester_nsa, provider_nsa



class RequesterService:

    def __init__(self, soap_resource, requester):

        self.requester = requester
        self.datetime_parser = parser.parser()

#        self.decoder = sudsservice.WSDLMarshaller(WSDL_REQUESTER % wsdl_dir)

        soap_resource.registerDecoder(actions.RESERVE_CONFIRMED, self.reserveConfirmed)

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


##    def _getGFTParameters(self, gft):
##        # GFT = GenericFailedType
##
##        requester_nsa, provider_nsa = _decodeNSAs(gft)
##        global_reservation_id       = str(gft.globalReservationId) if 'globalReservationId' in gft else None
##        connection_id               = str(gft.connectionId)
##        connection_state            = str(gft.connectionState)
##        error_id                    = None
##        error_message               = None
##        if 'serviceException' in gft:
##            error_id                = str(gft.serviceException.messageId) if 'messageId' in gft.serviceException else None
##            error_message           = str(gft.serviceException.text)      if 'text' in gft.serviceException else None
##
##        return requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_id, error_message


    def _createGenericAcknowledgement(self, _, correlation_id, requester_nsa, provider_nsa):

        header = HT.CommonHeaderType(None, correlation_id, requester_nsa, provider_nsa)

        f1 = StringIO.StringIO()
        header.export(f1,0, namespacedef_='xmlns:tns="%s"' % FRAMEWORK_TYPES_NS)
        header_payload = f1.getvalue()

        payload = minisoap.createSoapPayload(None, header_payload)
        return payload


    def reserveConfirmed(self, soap_action, soap_data):

        headers, bodies = minisoap.parseSoapPayload(soap_data)

        header = HT.parseString( ET.tostring( headers[0] ) )
        reservation = CT.parseString( ET.tostring( bodies[0] ) )

        if len(reservation.criteria) > 1:
            print "Multiple reservation criteria!"

        criteria = reservation.criteria[0]
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

        return self._createGenericAcknowledgement(None, reservation.globalReservationId, reservation.description, reservation.connectionId)


##    def reserveFailed(self, soap_action, soap_data):
##
##        assert soap_action == '"http://schemas.ogf.org/nsi/2011/10/connection/service/reserveFailed"'
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
##
##    def provisionConfirmed(self, soap_action, soap_data):
##
##        assert soap_action == '"http://schemas.ogf.org/nsi/2011/10/connection/service/provisionConfirmed"'
##        method, req = self.decoder.parse_request('provisionConfirmed', soap_data)
##
##        requester_nsa, provider_nsa = _decodeNSAs(req.provisionConfirmed)
##        correlation_id  = str(req.correlationId)
##        connection_id   = str(req.provisionConfirmed.connectionId)
##
##        d = self.requester.provisionConfirmed(correlation_id, requester_nsa, provider_nsa, None, connection_id)
##
##        reply = self.decoder.marshal_result(correlation_id, method)
##        return reply
##
##
##    def provisionFailed(self, soap_action, soap_data):
##
##        assert soap_action == '"http://schemas.ogf.org/nsi/2011/10/connection/service/provisionFailed"'
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
##
##    def releaseConfirmed(self, soap_action, soap_data):
##
##        assert soap_action == '"http://schemas.ogf.org/nsi/2011/10/connection/service/releaseConfirmed"'
##        method, req = self.decoder.parse_request('releaseConfirmed', soap_data)
##
##        requester_nsa, provider_nsa = _decodeNSAs(req.releaseConfirmed)
##        correlation_id  = str(req.correlationId)
##        connection_id   = str(req.releaseConfirmed.connectionId)
##
##        d = self.requester.releaseConfirmed(correlation_id, requester_nsa, provider_nsa, None, connection_id)
##
##        reply = self.decoder.marshal_result(correlation_id, method)
##        return reply
##
##
##    def releaseFailed(self, soap_action, soap_data):
##
##        assert soap_action == '"http://schemas.ogf.org/nsi/2011/10/connection/service/releaseFailed"'
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
##
##    def terminateConfirmed(self, soap_action, soap_data):
##
##        assert soap_action == '"http://schemas.ogf.org/nsi/2011/10/connection/service/terminateConfirmed"'
##        method, req = self.decoder.parse_request('terminateConfirmed', soap_data)
##
##        requester_nsa, provider_nsa = _decodeNSAs(req.terminateConfirmed)
##        correlation_id  = str(req.correlationId)
##        connection_id   = str(req.terminateConfirmed.connectionId)
##
##        d = self.requester.terminateConfirmed(correlation_id, requester_nsa, provider_nsa, None, connection_id)
##
##        reply = self.decoder.marshal_result(correlation_id, method)
##        return reply
##
##
##    def terminateFailed(self, soap_action, soap_data):
##
##        assert soap_action == '"http://schemas.ogf.org/nsi/2011/10/connection/service/terminateFailed"'
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
##
##    def queryConfirmed(self, soap_action, soap_data):
##
##        assert soap_action == '"http://schemas.ogf.org/nsi/2011/10/connection/service/queryConfirmed"'
##        method, req = self.decoder.parse_request('queryConfirmed', soap_data)
##
##        requester_nsa, provider_nsa = _decodeNSAs(req.queryConfirmed)
##
##        correlation_id          = str(req.correlationId)
##        #reservation_summary     = req.queryConfirmed
##        #connection_id           = str(req.terminateConfirmed.connectionId)
##
##        # should really translate this to something generic
##        # need to know if summary or details parameters was given though :-/
##        query_result = req.queryConfirmed
##
##        d = self.requester.queryConfirmed(correlation_id, requester_nsa, provider_nsa, query_result)
##
##        reply = self.decoder.marshal_result(correlation_id, method)
##        return reply
##
##
##    def queryFailed(self, soap_action, soap_data):
##
##        assert soap_action == '"http://schemas.ogf.org/nsi/2011/10/connection/service/queryFailed"'
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
