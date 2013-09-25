"""
Various helper functions for nsi2 protocol stack.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012)
"""

from xml.etree import ElementTree as ET

from twisted.python import log

from opennsa import constants as cnt, nsa, error
from opennsa.protocols.shared import minisoap
from opennsa.protocols.nsi2.bindings import nsiframework, nsiconnection, p2pservices


LOG_SYSTEM = 'NSI2.Helper'

# don't really fit anywhere, consider cramming them into the bindings
FRAMEWORK_TYPES_NS   = "http://schemas.ogf.org/nsi/2013/07/framework/types"
FRAMEWORK_HEADERS_NS = "http://schemas.ogf.org/nsi/2013/07/framework/headers"
CONNECTION_TYPES_NS  = "http://schemas.ogf.org/nsi/2013/07/connection/types"
SERVICE_TYPES_NS     = 'http://schemas.ogf.org/nsi/2013/07/services/types'
P2PSERVICES_TYPES_NS = 'http://schemas.ogf.org/nsi/2013/07/services/point2point'

URN_NETWORK = 'urn:ogf:network:'

ET.register_namespace('ftypes', FRAMEWORK_TYPES_NS)
ET.register_namespace('header', FRAMEWORK_HEADERS_NS)
ET.register_namespace('ctypes', CONNECTION_TYPES_NS)
ET.register_namespace('stypes', SERVICE_TYPES_NS)
ET.register_namespace('p2psrv', P2PSERVICES_TYPES_NS)



def createHeader(requester_nsa_urn, provider_nsa_urn, session_security_attrs=None, reply_to=None, correlation_id=None):

    header = nsiframework.CommonHeaderType(cnt.CS2_SERVICE_TYPE, correlation_id, requester_nsa_urn, provider_nsa_urn, reply_to, session_security_attrs)
    header_element = header.xml(nsiframework.nsiHeader)
    return header_element


def createGenericAcknowledgement(header):

    soap_header = nsiframework.CommonHeaderType(cnt.CS2_SERVICE_TYPE, header.correlation_id, header.requester_nsa, header.provider_nsa, None, header.session_security_attrs)
    soap_header_element = soap_header.xml(nsiframework.nsiHeader)

    generic_confirm = nsiconnection.GenericAcknowledgmentType()
    generic_confirm_element = generic_confirm.xml(nsiconnection.acknowledgment)

    payload = minisoap.createSoapPayload(generic_confirm_element, soap_header_element)
    return payload


def createServiceException(err, provider_nsa, connection_id=None, service_type=None):

    variables = None
    child_exception = None

    if err.check(error.NSIError):
        error_id = err.value.errorId
        #se = bindings.ServiceExceptionType(provider_nsa, connection_id, err.value.errorId, err.getErrorMessage(), variables, child_exception)
    else:
        log.msg('Got a non NSIError exception: %s : %s' % (err.value.__class__.__name__, err.getErrorMessage()), system=LOG_SYSTEM)
        log.msg('Cannot create detailed service exception, defaulting to NSI InternalServerError (00500)', system=LOG_SYSTEM)
        log.err(err)
        error_id = error.InternalServerError.errorId
        #se = bindings.ServiceExceptionType(provider_nsa, connection_id, error.InternalServerError.errorId, err.getErrorMessage(), variables, child_exception)

    se = nsiframework.ServiceExceptionType(provider_nsa, connection_id, service_type, error_id, err.getErrorMessage(), variables, child_exception)

    return se


def parseRequest(soap_data):

    headers, bodies = minisoap.parseSoapPayload(soap_data)

    if headers is None:
        raise ValueError('No header specified in payload')
        #raise resource.SOAPFault('No header specified in payload')

    # more checking here...

    header = nsiframework.parseElement(headers[0])
    body   = nsiconnection.parseElement(bodies[0])

    nsi_header = nsa.NSIHeader(header.requesterNSA, header.providerNSA, None, header.correlationId, header.replyTo)

    return nsi_header, body


def createXMLTime(timestamp):
    # we assume this is without tz info and in utc time, because that is how it should be in opennsa
    assert timestamp.tzinfo is None, 'timestamp must be without time zone information'
    return timestamp.isoformat() + 'Z'


def createLabel(type_value_pair):
    if type_value_pair.targetNamespace:
        label_type = '{%s}%s' % (type_value_pair.targetNamespace, type_value_pair.type_)
    else:
        label_type = type_value_pair.type_
    return nsa.Label(label_type, type_value_pair.value)


def createSTP(stp_type):

    if not stp_type.networkId.startswith(URN_NETWORK):
        raise error.PayloadError('STP networkId (%s) did not start with %s' % (stp_type.networkId, URN_NETWORK))

    network = stp_type.networkId.replace(URN_NETWORK, '')

    if not stp_type.localId.startswith(URN_NETWORK):
        raise error.PayloadError('STP localId (%s) did not start with %s' % (stp_type.localId, URN_NETWORK))

    local_id = stp_type.localId.replace(stp_type.networkId + ':', '')

    if stp_type.labels is not None:
        labels = [ createLabel(tvp) for tvp in stp_type.labels ]
    else:
        labels = []

    return nsa.STP(network, local_id, labels)


def createSTPType(stp):

    def createValue(v1, v2):
        if v1 == v2:
            return str(v1)
        else:
            return str(v1) + '-' + str(v2)

    def splitLabelType(label_type):
        if '{' in label_type:
            ns, tag = label_type.split('}',1)
            ns = ns[1:]
        else:
            ns, tag = None, label_type
        return ns, tag

    labels = None
    if stp.labels not in (None, []):
        labels = []
        for label in stp.labels:
            ns, tag = splitLabelType(label.type_)
            labels.append( nsiconnection.TypeValuePairType(tag, ns, [ label.labelValue() ] ) )

    network = URN_NETWORK + stp.network
    port = stp.port

    return p2pservices.StpType(network, network + ':' + port, labels)



def buildQuerySummaryResult(query_confirmed):

    reservations = []
    for resv in query_confirmed.reservations:

        r_states    = resv.connectionStates
        r_dps       = r_states.dataPlaneStatus

        dps = (r_dps.active, r_dps.version, r_dps.versionConsistent)
        states = (r_states.reservationState, r_states.provisionState, r_states.lifecycleState, dps)

        criterias = []
        if resv.criteria is not None:
            for rc in resv.criteria:
                rp = rc.path
                source_stp = createSTP(rp.sourceSTP)
                dest_stp   = createSTP(rp.destSTP)
                crit = nsa.ServiceParameters(rc.schedule.startTime, rc.schedule.endTime, source_stp, dest_stp, rc.bandwidth, directionality=rp.directionality, version=int(rc.version))
                criterias.append(crit)

        reservations.append( ( resv.connectionId, resv.globalReservationId, resv.description, criterias, resv.requesterNSA, states, resv.notificationId) )

    return reservations


def buildQuerySummaryResultType(reservations):

    query_results = []

    for rsv in reservations:

        cid, gid, desc, crits, req_nsa, states, nid = rsv
        rsm, psm, lsm, dsm = states

        criterias = []
        for crit in crits:
            schedule   = nsiconnection.ScheduleType( createXMLTime(crit.start_time), createXMLTime(crit.end_time) )
            source_stp = createSTPType(crit.source_stp)
            dest_stp   = createSTPType(crit.dest_stp)
            path       = nsiconnection.PathType('Bidirectional', False, source_stp, dest_stp, None)
            criteria   = nsiconnection.QuerySummaryResultCriteriaType(crit.version, schedule, crit.bandwidth, None, path, None)
            criterias.append(criteria)

        data_plane_status = nsiconnection.DataPlaneStatusType(dsm[0], dsm[1], dsm[2])
        connection_states = nsiconnection.ConnectionStatesType(rsm, psm, lsm, data_plane_status)

        qsrt = nsiconnection.QuerySummaryResultType(cid, gid, desc, criterias, req_nsa, connection_states, nid)
        query_results.append(qsrt)

    qsc = nsiconnection.QuerySummaryConfirmedType(query_results)
    return qsc

