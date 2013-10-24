"""
Various helper functions for nsi2 protocol stack.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012)
"""

from xml.etree import ElementTree as ET

from dateutil import parser
from dateutil.tz import tzutc

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
    elif len(headers) > 1:
        raise ValueError('Multiple headers specified in payload')

    header = nsiframework.parseElement(headers[0])
    if header.protocolVersion != cnt.CS2_SERVICE_TYPE:
        raise ValueError('Invalid protocol "%s". Only %s supported' % (header.protocolVersion, cnt.CS2_SERVICE_TYPE))

    if len(bodies) == 0:
        body = None
    elif len(bodies) == 1:
        body = nsiconnection.parseElement(bodies[0])
    else:
        body = [ nsiconnection.parseElement(b) for b in bodies ]

    nsi_header = nsa.NSIHeader(header.requesterNSA, header.providerNSA, None, header.correlationId, header.replyTo)

    return nsi_header, body


def createXMLTime(timestamp):
    # we assume this is without tz info and in utc time, because that is how it should be in opennsa
    assert timestamp.tzinfo is None, 'timestamp must be without time zone information'
    return timestamp.isoformat() + 'Z'


def parseXMLTimestamp(xsd_timestamp):

    xtp = parser.parser()

    dt = xtp.parse(xsd_timestamp)
    if dt.utcoffset() is None:
        raise error.PayloadError('Timestamp has no time zone information')

    # convert to utc and remove tz info (internal use)
    utc_dt = dt.astimezone(tzutc()).replace(tzinfo=None)
    return utc_dt



def createLabel(type_value_pair):
    if type_value_pair.targetNamespace:
        label_type = '{%s}%s' % (type_value_pair.targetNamespace, type_value_pair.type_)
    else:
        label_type = type_value_pair.type_
    return nsa.Label(label_type, type_value_pair.value)


def createSTP(stp_type):

    if not stp_type.networkId.startswith(URN_NETWORK):
        raise error.PayloadError('STP networkId (%s) did not start with %s' % (stp_type.networkId, URN_NETWORK))

    network_id = stp_type.networkId.replace(URN_NETWORK, '')

    if not stp_type.localId.startswith(URN_NETWORK):
        raise error.PayloadError('STP localId (%s) did not start with %s' % (stp_type.localId, URN_NETWORK))

    local_id = stp_type.localId.replace(URN_NETWORK, '')

    if stp_type.labels is not None:
        labels = [ createLabel(tvp) for tvp in stp_type.labels ]
    else:
        labels = []

    return nsa.STP(network_id, local_id, labels)


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

    network_id = URN_NETWORK + stp.network
    local_id = URN_NETWORK + stp.port

    return p2pservices.StpType(network_id, local_id, labels)



def buildQuerySummaryResult(query_confirmed):

    qc = query_confirmed

    r_states    = qc.connectionStates
    r_dps       = r_states.dataPlaneStatus

    dps = (r_dps.active, r_dps.version, r_dps.versionConsistent)
    states = (r_states.reservationState, r_states.provisionState, r_states.lifecycleState, dps)

    criterias = []
    if qc.criteria is not None:
        for rc in qc.criteria:

            start_time = parseXMLTimestamp(rc.schedule.startTime)
            end_time   = parseXMLTimestamp(rc.schedule.endTime)
            schedule = nsa.Schedule(start_time, end_time)

            # service definition stuff not quite done yet
            #source_stp = createSTP(rp.sourceSTP)
            #dest_stp   = createSTP(rp.destSTP)

            #sd = nsa.EthernetVLANService(source_stp, dest_stp, c.bandwidth, 1, 1)
            sd = None
            crit = nsa.Criteria(rc.version, schedule, sd)
            criterias.append(crit)

    reservation = ( qc.connectionId, qc.globalReservationId, qc.description, criterias, qc.requesterNSA, states, qc.notificationId)
    return reservation



def buildQuerySummaryResultType(reservations):

    query_results = []

    for rsv in reservations:

        cid, gid, desc, crits, req_nsa, states, nid = rsv
        rsm, psm, lsm, dsm = states

        criterias = []
        for crit in crits:
            schedule = nsiconnection.ScheduleType(createXMLTime(crit.schedule.start_time), createXMLTime(crit.schedule.end_time))
            service_type = cnt.EVTS_AGOLE if type(crit.service_def) is nsa.EthernetVLANService else 'n/a'
            children = []
            criteria = nsiconnection.QuerySummaryResultCriteriaType(crit.revision, schedule, service_type, children)
            criterias.append(criteria)

        data_plane_status = nsiconnection.DataPlaneStatusType(dsm[0], dsm[1], dsm[2])
        connection_states = nsiconnection.ConnectionStatesType(rsm, psm, lsm, data_plane_status)

        qsrt = nsiconnection.QuerySummaryResultType(cid, gid, desc, criterias, req_nsa, connection_states, nid)
        query_results.append(qsrt)

    return query_results

