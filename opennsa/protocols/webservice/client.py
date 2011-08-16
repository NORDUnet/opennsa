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


    def reserve(self, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters):
        # reserve(xs:anyURI transactionId, xs:anyURI replyTo, ns1:ReserveType reserveRequest, )

        correlation_id = self._createCorrelationId()

        res_req = self.provider_client.createType('{http://schemas.ogf.org/nsi/2011/07/connection/types}ReservationType')

        res_req.requesterNSA                = requester_nsa.uri()
        res_req.providerNSA                 = provider_nsa.uri()

        res_req.reservation.connectionId    = connection_id

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


    def reserveConfirmed(self, requester_nsa, provider_nsa, global_reservation_id, description, connection_id, service_parameters):
        raise NotImplementedError('OpenNSA WS protocol under development')

    def reserveFailed(self, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, service_exception):
        raise NotImplementedError('OpenNSA WS protocol under development')

    def terminateReservation(self, requester_nsa, provider_nsa, session_security_attr, connection_id):
        raise NotImplementedError('OpenNSA WS protocol under development')

    def provision(self, requester_nsa, provider_nsa, session_security_attr, connection_id):
        raise NotImplementedError('OpenNSA WS protocol under development')

    def releaseProvision(self, requester_nsa, provider_nsa, session_security_attr, connection_id):
        raise NotImplementedError('OpenNSA WS protocol under development')

    def query(self, requester_nsa, provider_nsa, session_security_attr, query_filter):
        raise NotImplementedError('OpenNSA WS protocol under development')

