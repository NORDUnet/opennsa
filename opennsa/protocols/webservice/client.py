"""
Web Service protocol for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import uuid

from twisted.python import log

from opennsa.protocols.webservice.ext import twistedsuds


#import os
#WSDL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__),"../../../wsdl/"))
WSDL_PROVIDER   = 'file://%s/ogf_nsi_connection_provider_v1_0.wsdl'
WSDL_REQUESTER  = 'file://%s/ogf_nsi_connection_requester_v1_0.wsdl'


URN_UUID_PREFIX = 'urn:uuid:'


def utcTime(dt):
    return dt.isoformat().rsplit('.',1)[0] + 'Z'


def createCorrelationId():
    return URN_UUID_PREFIX + str(uuid.uuid1())


class ProviderClient:

    def __init__(self, reply_to, wsdl_dir, ctx_factory=None):

        self.reply_to = reply_to
        self.client = twistedsuds.TwistedSUDSClient(WSDL_PROVIDER % wsdl_dir, ctx_factory=ctx_factory)


    def _createGenericRequestType(self, requester_nsa, provider_nsa, connection_id):

        req = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}GenericRequestType')
        req.requesterNSA = requester_nsa.urn()
        req.providerNSA  = provider_nsa.urn()
        req.connectionId = connection_id
        return req


    def reserve(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters):

        res_req = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}ReserveType')

        res_req.requesterNSA                = requester_nsa.urn()
        res_req.providerNSA                 = provider_nsa.urn()

        #<sessionSecurityAttr>
        #    <ns5:Attribute Name="globalUserName" NameFormat="urn:oasis:names:tc:SAML:2.0:attrname-format:basic">
        #        <ns5:AttributeValue xsi:type="xs:string" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">jrv@internet2.edu</ns5:AttributeValue>
        #    </ns5:Attribute>
        #    <ns5:Attribute Name="role" NameFormat="urn:oasis:names:tc:SAML:2.0:attrname-format:basic">
        #        <ns5:AttributeValue xsi:type="xs:string" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">AuthorizedUser</ns5:AttributeValue>
        #    </ns5:Attribute>
        #</sessionSecurityAttr>

        # OK, giving up for now, SUDS refuses to put the right namespace on this
        #user_attr = self.client.createType('{urn:oasis:names:tc:SAML:2.0:assertion}Attribute')
        #user_attr._Name = 'globalUserName'
        #user_attr._NameFormat = 'urn:oasis:names:tc:SAML:2.0:attrname-format:basic'
        #user_attr.AttributeValue = ['jrv@internet2.edu']
        #role_attr = self.client.createType('{urn:oasis:names:tc:SAML:2.0:assertion}Attribute')
        #role_attr._Name = 'role'
        #role_attr._NameFormat = 'urn:oasis:names:tc:SAML:2.0:attrname-format:basic'
        #role_attr.AttributeValue = ['AuthorizedUser']
        #res_req.sessionSecurityAttr['Attribute'] = [ user_attr, role_attr ]

        res_req.reservation.globalReservationId     = global_reservation_id
        res_req.reservation.description             = description
        res_req.reservation.connectionId            = connection_id

        res_req.reservation.path.directionality     = service_parameters.directionality
        res_req.reservation.path.sourceSTP.stpId    = service_parameters.source_stp.urn()
        #res_req.reservation.path.sourceSTP.stpSpecAttrs.guaranteed = ['123' ]
        #res_req.reservation.path.sourceSTP.stpSpecAttrs.preferred =  ['abc', 'def']
        res_req.reservation.path.destSTP.stpId      = service_parameters.dest_stp.urn()

        res_req.reservation.serviceParameters.schedule.startTime    = utcTime(service_parameters.start_time)
        res_req.reservation.serviceParameters.schedule.endTime      = utcTime(service_parameters.end_time)
        res_req.reservation.serviceParameters.bandwidth.desired     = service_parameters.bandwidth.desired
        res_req.reservation.serviceParameters.bandwidth.minimum     = service_parameters.bandwidth.minimum
        res_req.reservation.serviceParameters.bandwidth.maximum     = service_parameters.bandwidth.maximum
        #res_req.reservation.serviceParameters.serviceAttributes.guaranteed = [ '1a' ]
        #res_req.reservation.serviceParameters.serviceAttributes.preferred  = [ '2c', '3d' ]

        d = self.client.invoke(provider_nsa.url(), 'reserve', correlation_id, self.reply_to, res_req)
        return d


    def provision(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id):

        req = self._createGenericRequestType(requester_nsa, provider_nsa, connection_id)
        d = self.client.invoke(provider_nsa.url(), 'provision', correlation_id, self.reply_to, req)
        return d


    def release(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id):

        req = self._createGenericRequestType(requester_nsa, provider_nsa, connection_id)
        d = self.client.invoke(provider_nsa.url(), 'release', correlation_id, self.reply_to, req)
        return d


    def terminate(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, connection_id):

        req = self._createGenericRequestType(requester_nsa, provider_nsa, connection_id)
        d = self.client.invoke(provider_nsa.url(), 'terminate', correlation_id, self.reply_to, req)
        return d


    def query(self, correlation_id, requester_nsa, provider_nsa, session_security_attr, operation="Summary", connection_ids=None, global_reservation_ids=None):

        req = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}QueryType')
        #print req

        req.requesterNSA = requester_nsa.urn()
        req.providerNSA  = provider_nsa.urn()
        req.operation = operation
        req.queryFilter.connectionId = connection_ids or []
        req.queryFilter.globalReservationId = global_reservation_ids or []
        #print req

        d = self.client.invoke(provider_nsa.url(), 'query', correlation_id, self.reply_to, req)
        return d




class RequesterClient:

    def __init__(self, wsdl_dir):

        self.client = twistedsuds.TwistedSUDSClient(WSDL_REQUESTER % wsdl_dir)


    def _createGenericConfirmType(self, requester_nsa, provider_nsa, global_reservation_id, connection_id):

        conf = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}GenericConfirmedType')
        conf.requesterNSA        = requester_nsa
        conf.providerNSA         = provider_nsa
        conf.globalReservationId = global_reservation_id
        conf.connectionId        = connection_id
        return conf


    def reserveConfirmed(self, requester_uri, correlation_id, requester_nsa, provider_nsa, global_reservation_id, description, connection_id, service_parameters):

        #correlation_id = self._createCorrelationId()

        res_conf = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}ReserveConfirmedType')

        res_conf.requesterNSA   = requester_nsa
        res_conf.providerNSA    = provider_nsa

        res_conf.reservation.globalReservationId    = global_reservation_id
        res_conf.reservation.description            = description
        res_conf.reservation.connectionId           = connection_id
        #res_conf.reservation.connectionState        = 'Reserved' # not sure why this doesn't work

        res_conf.reservation.serviceParameters.schedule.startTime     = utcTime(service_parameters.start_time)
        res_conf.reservation.serviceParameters.schedule.endTime       = utcTime(service_parameters.end_time)

        res_conf.reservation.serviceParameters.bandwidth.desired      = service_parameters.bandwidth.desired
        res_conf.reservation.serviceParameters.bandwidth.minimum      = service_parameters.bandwidth.minimum
        res_conf.reservation.serviceParameters.bandwidth.maximum      = service_parameters.bandwidth.maximum

        res_conf.reservation.path.directionality  = service_parameters.directionality
        res_conf.reservation.path.sourceSTP.stpId = service_parameters.source_stp.urn()
        res_conf.reservation.path.destSTP.stpId   = service_parameters.dest_stp.urn()

        d = self.client.invoke(requester_uri, 'reserveConfirmed', correlation_id, res_conf)
        return d


    def reserveFailed(self, requester_uri, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_msg):

        res_fail = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}GenericFailedType')
        nsi_ex   = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}ServiceExceptionType')

        res_fail.requesterNSA   = requester_nsa
        res_fail.providerNSA    = provider_nsa

        res_fail.globalReservationId    = global_reservation_id
        res_fail.connectionId           = connection_id
        res_fail.connectionState        = connection_state

        nsi_ex.errorId = 'RESERVATION_FAILURE'
        nsi_ex.text = error_msg
        res_fail.serviceException = nsi_ex

        d = self.client.invoke(requester_uri, 'reserveFailed', correlation_id, res_fail)
        return d


    def provisionConfirmed(self, requester_uri, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id):

        conf = self._createGenericConfirmType(requester_nsa, provider_nsa, global_reservation_id, connection_id)
        d = self.client.invoke(requester_uri, 'provisionConfirmed', correlation_id, conf)
        return d


    def provisionFailed(self, requester_uri, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_msg):

        gft = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}GenericFailedType')
        net = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}ServiceExceptionType')

        gft.requesterNSA   = requester_nsa
        gft.providerNSA    = provider_nsa

        gft.globalReservationId    = global_reservation_id
        gft.connectionId           = connection_id
        gft.connectionState        = connection_state

        net.errorId = 'PROVISION_FAILURE'
        net.text = error_msg
        gft.serviceException = net

        d = self.client.invoke(requester_uri, 'provisionFailed', correlation_id, gft)
        return d


    def releaseConfirmed(self, requester_uri, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id):

        conf = self._createGenericConfirmType(requester_nsa, provider_nsa, global_reservation_id, connection_id)
        d = self.client.invoke(requester_uri, 'releaseConfirmed', correlation_id, conf)
        return d


    def releaseFailed(self, requester_uri, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_msg):

        gft = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}GenericFailedType')
        net = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}ServiceExceptionType')

        gft.requesterNSA   = requester_nsa
        gft.providerNSA    = provider_nsa

        gft.globalReservationId    = global_reservation_id
        gft.connectionId           = connection_id
        gft.connectionState        = connection_state

        net.errorId = 'RELEASE_FAILURE'
        net.text = error_msg
        gft.serviceException = net

        d = self.client.invoke(requester_uri, 'releaseFailed', correlation_id, gft)
        return d


    def terminateConfirmed(self, requester_uri, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id):

        conf = self._createGenericConfirmType(requester_nsa, provider_nsa, global_reservation_id, connection_id)
        d = self.client.invoke(requester_uri, 'terminateConfirmed', correlation_id, conf)
        return d


    def terminateFailed(self, requester_uri, correlation_id, requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, error_msg):

        gft = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}GenericFailedType')
        net = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}ServiceExceptionType')

        gft.requesterNSA   = requester_nsa
        gft.providerNSA    = provider_nsa

        gft.globalReservationId    = global_reservation_id
        gft.connectionId           = connection_id
        gft.connectionState        = connection_state

        net.errorId = 'TERMINATE_FAILURE'
        net.text = error_msg
        gft.serviceException = net

        d = self.client.invoke(requester_uri, 'terminateFailed', correlation_id, gft)
        return d


    def queryConfirmed(self, requester_uri, correlation_id, requester_nsa, provider_nsa, operation, connections):

        res = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}QueryConfirmedType')
        res.requesterNSA = requester_nsa
        res.providerNSA  = provider_nsa

        if operation == "Summary":
            qsrs = []
            for conn in connections:
                qsr = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}QuerySummaryResultType')
                #print qsr
                qsr.globalReservationId = conn.global_reservation_id
                qsr.description         = conn.description
                qsr.connectionId        = conn.connection_id
                qsr.connectionState     = conn.state()

                qsr.path.sourceSTP.stpId    = conn.source_stp.urn()
                qsr.path.destSTP.stpId      = conn.dest_stp.urn()

                qsr.serviceParameters.schedule.startTime = utcTime(conn.service_parameters.start_time)
                qsr.serviceParameters.schedule.endTime   = utcTime(conn.service_parameters.end_time)

                qsr.serviceParameters.bandwidth.desired  = conn.service_parameters.bandwidth.desired
                qsr.serviceParameters.bandwidth.minimum  = conn.service_parameters.bandwidth.minimum
                qsr.serviceParameters.bandwidth.maximum  = conn.service_parameters.bandwidth.maximum

                def createOrderedSTP(stp, rank):
                    ostp = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}OrderedServiceTerminationPointType')
                    ostp.stpId = stp.urn()
                    ostp._order = rank
                    return ostp

                # create list of all stps, but skip source and dest stp
                stps = [ stp for sc in conn.connections() for stp in sc.stps() ] [1:-1]
                for i, stp in zip(range(len(stps)), stps):
                    qsr.path.stpList.stp.append( createOrderedSTP(stp, i) )

                qsrs.append(qsr)

            res.reservationSummary = qsrs

        elif operation == "Details":
            qdr = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}QueryDetailsResultType')
            #print qdr
            qdr.globalReservationId = '123'
            res.reservationDetails = [ qdr ]

        else:
            raise ValueError('Invalid query operation type')

        d = self.client.invoke(requester_uri, 'queryConfirmed', correlation_id, res)
        return d


    def queryFailed(self, requester_uri, correlation_id, requester_nsa, provider_nsa, error_msg):

        print "CLIENT QUERY FAILED"
        qft = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}QueryFailedType')
        net = self.client.createType('{http://schemas.ogf.org/nsi/2011/10/connection/types}ServiceExceptionType')

        qft.requesterNSA = requester_nsa
        qft.providerNSA  = provider_nsa

        net.errorId = 'QUERY_FAILURE'
        net.text = error_msg
        qft.serviceException = net

        d = self.client.invoke(requester_uri, 'queryFailed', correlation_id, qft)
        return d

