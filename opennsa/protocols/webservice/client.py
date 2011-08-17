"""
Web Service protocol for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import uuid

from zope.interface import implements

from twisted.python import log

from opennsa.interface import NSIInterface
from opennsa.protocols.webservice.ext import twistedsuds



WSDL_PROVIDER   = 'file:///home/htj/nsi/opennsa/wsdl/ogf_nsi_connection_provider_v1_0.wsdl'
WSDL_REQUESTER  = 'file:///home/htj/nsi/opennsa/wsdl/ogf_nsi_connection_requester_v1_0.wsdl'



class NSIWebServiceClient:

    implements(NSIInterface)

    def __init__(self, reply_to):

        self.provider_client  = twistedsuds.TwistedSUDSClient(WSDL_PROVIDER)
        self.requester_client = twistedsuds.TwistedSUDSClient(WSDL_REQUESTER)

        self.reply_to = reply_to


    def _createCorrelationId(self):
        return uuid.uuid1().int

    def _createGenericRequestType(self, requester_nsa, provider_nsa, connection_id):

        req = self.provider_client.createType('{http://schemas.ogf.org/nsi/2011/07/connection/types}GenericRequestType')
        req.requesterNSA = requester_nsa.uri()
        req.providerNSA  = provider_nsa.uri()
        req.connectionId = connection_id
        return req


    def reserve(self, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters):
        # reserve(xs:anyURI transactionId, xs:anyURI replyTo, ns1:ReserveType reserveRequest, )

        correlation_id = self._createCorrelationId()

        res_req = self.provider_client.createType('{http://schemas.ogf.org/nsi/2011/07/connection/types}ReservationType')

        res_req.requesterNSA                = requester_nsa.uri()
        res_req.providerNSA                 = provider_nsa.uri()

        res_req.reservation.globalReservationId     = global_reservation_id
        res_req.reservation.description             = description
        res_req.reservation.connectionId            = connection_id

        res_req.reservation.path.directionality     = service_parameters.directionality
        res_req.reservation.path.sourceSTP.stpId    = service_parameters.source_stp.uri()
        #res_req.reservation.path.sourceSTP.stpSpecAttrs.guaranteed = ['123' ]
        #res_req.reservation.path.sourceSTP.stpSpecAttrs.preferred =  ['abc', 'def']
        res_req.reservation.path.destSTP.stpId      = service_parameters.dest_stp.uri()

        res_req.reservation.serviceParameters.schedule.startTime    = service_parameters.start_time
        res_req.reservation.serviceParameters.schedule.endTime      = service_parameters.end_time
        res_req.reservation.serviceParameters.bandwidth.desired     = service_parameters.bandwidth_desired
        res_req.reservation.serviceParameters.bandwidth.minimum     = service_parameters.bandwidth_minimum
        res_req.reservation.serviceParameters.bandwidth.maximum     = service_parameters.bandwidth_maximum
        #res_req.reservation.serviceParameters.serviceAttributes.guaranteed = [ '1a' ]
        #res_req.reservation.serviceParameters.serviceAttributes.preferred  = [ '2c', '3d' ]

        d = self.provider_client.invoke(provider_nsa.uri(), 'reservation', correlation_id, self.reply_to, res_req)
        return d


    def reservationConfirmed(self, requester_nsa, provider_nsa, global_reservation_id, description, connection_id, service_parameters, reply_to):

        correlation_id = self._createCorrelationId()

        res_conf = self.requester_client.createType('{http://schemas.ogf.org/nsi/2011/07/connection/types}ReservationConfirmedType')

        res_conf.requesterNSA   = requester_nsa.uri()
        res_conf.providerNSA    = provider_nsa.uri()

        res_conf.reservation.globalReservationId    = global_reservation_id
        res_conf.reservation.description            = description
        res_conf.reservation.connectionId           = connection_id

        d = self.requester_client.invoke(str(reply_to), 'reservationConfirmed', correlation_id, res_conf)
        return d


    def reservationFailed(self, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, service_exception):
        raise NotImplementedError('OpenNSA WS protocol under development')


    def terminateReservation(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        correlation_id = self._createCorrelationId()
        req = self._createGenericRequestType(requester_nsa, provider_nsa, connection_id)
        d = self.provider_client.invoke(provider_nsa.uri(), 'terminate', correlation_id, self.reply_to, req)
        return d


    def provision(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        correlation_id = self._createCorrelationId()
        req = self._createGenericRequestType(requester_nsa, provider_nsa, connection_id)
        d = self.provider_client.invoke(provider_nsa.uri(), 'provision', correlation_id, self.reply_to, req)
        return d


    def releaseProvision(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        correlation_id = self._createCorrelationId()
        req = self._createGenericRequestType(requester_nsa, provider_nsa, connection_id)
        d = self.provider_client.invoke(provider_nsa.uri(), 'release', correlation_id, self.reply_to, req)
        return d


    def query(self, requester_nsa, provider_nsa, session_security_attr, query_filter):
        raise NotImplementedError('OpenNSA WS protocol under development')

