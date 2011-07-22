"""
Web Service protocol for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import uuid

from zope.interface import implements

from twisted.python import log
#from twisted.web import client

from suds.client import Client, SoapClient
from suds.bindings import binding, rpc, document

from opennsa.interface import NSIInterface
from opennsa.protocol.webservice import soap as nsisoap


class WebServiceNSIClient:

    implements(NSIInterface)

    def __init__(self, reply_to):

        self.reply_to = reply_to or 'http://localhost:7080/NSI/services/ConnectionService' # remove once testing is done

        wsdl = 'file:///home/htj/nsi/opennsa/wsdl/ogf_nsi_connection_service_v1_0.wsdl'

        self.ws_client = Client(wsdl)


    def _createTransactionId(self):
        return uuid.uuid1().int


    def reserve(self, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters):
        # reserve(xs:anyURI transactionId, xs:anyURI replyTo, ns1:ReserveType reserveRequest, )

        transaction_id = 'sager'

        reserve = self.ws_client.factory.create('ns1:ReserveType')
        # print reserve

        #reserve.requestorNSA.nsaAddress = 'http://localhost:7080/NSI/services/ConnectionService'
        #reserve.providerNSA.nsaAddress = 'http://localhost:9080/NSI/services/ConnectionService'
        reserve.requestorNSA.nsaAddress = requester_nsa.address
        reserve.providerNSA.nsaAddress = provider_nsa.address

        reserve.reservation.connectionId = connection_id

        reserve.reservation.serviceParameters.schedule.startTime = service_parameters.start_time
        reserve.reservation.serviceParameters.schedule.endTime   = service_parameters.end_time

        # reserve.reservation.serviceParameters.bandwidth.desired = '1000'
        # reserve.reservation.serviceParameters.bandwidth.minimum = '500'
        # reserve.reservation.serviceParameters.bandwidth.maximum = '1200'
        # reserve.reservation.serviceParameters.directionality.value = 'unidirectional'

        reserve.reservation.serviceParameters.pathObject.sourceSTP.networkId = service_parameters.source_stp.network
        reserve.reservation.serviceParameters.pathObject.sourceSTP.localId   = service_parameters.source_stp.endpoint
        # reserve.reservation.serviceParameters.pathObject.sourceSTP.stpSpecAttrs.guaranteed.attribute = ['123' ]
        # reserve.reservation.serviceParameters.pathObject.sourceSTP.stpSpecAttrs.preferred.attribute =  ['abc', 'def']

        reserve.reservation.serviceParameters.pathObject.destSTP.networkId   = service_parameters.dest_stp.network
        reserve.reservation.serviceParameters.pathObject.destSTP.localId     = service_parameters.dest_stp.endpoint
        # reserve.reservation.serviceParameters.pathObject.destSTP.stpSpecAttrs.guaranteed.attribute =  [ 'dfg', 'jkl' ]
        # reserve.reservation.serviceParameters.pathObject.destSTP.stpSpecAttrs.preferred.attribute =   [ '234', '567' ]

        # reserve.reservation.serviceParameters.serviceAttrs.guaranteed = [ '1a' ]
        # reserve.reservation.serviceParameters.serviceAttrs.preferred  = [ '2c', '3d' ]

        method = self.ws_client.service.reserve

        doc = document.Document(self.ws_client.wsdl)

        # schema = b.wsdl.schema
        # RESERVE_TYPE = ('ReserveType', 'http://schemas.ogf.org/nsi/2011/07/connection/types')
        # schema_type = schema.types[RESERVE_TYPE]

        args = (transaction_id, self.reply_to, reserve)
        soapenv = doc.get_message(method.method, args, kwargs={})
        r = str(soapenv)

        print "R",r 

        #parseSOAPEnvelope(r, b.wsdl.schema, rrt)


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

