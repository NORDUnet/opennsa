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
FRAMEWORK_TYPES_NS   = "http://schemas.ogf.org/nsi/2013/12/framework/types"
FRAMEWORK_HEADERS_NS = "http://schemas.ogf.org/nsi/2013/12/framework/headers"
CONNECTION_TYPES_NS  = "http://schemas.ogf.org/nsi/2013/12/connection/types"
SERVICE_TYPES_NS     = 'http://schemas.ogf.org/nsi/2013/12/services/types'
P2PSERVICES_TYPES_NS = 'http://schemas.ogf.org/nsi/2013/12/services/point2point'

URN_NETWORK = 'urn:ogf:network:'

ET.register_namespace('ftypes', FRAMEWORK_TYPES_NS)
ET.register_namespace('header', FRAMEWORK_HEADERS_NS)
ET.register_namespace('ctypes', CONNECTION_TYPES_NS)
ET.register_namespace('stypes', SERVICE_TYPES_NS)
ET.register_namespace('p2psrv', P2PSERVICES_TYPES_NS)

# Lookup table for urn labels
LABEL_MAP = {
    'vlan' : cnt.ETHERNET_VLAN
}



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
    #if header.protocolVersion != cnt.CS2_SERVICE_TYPE:
    #    raise ValueError('Invalid protocol "%s". Only %s supported' % (header.protocolVersion, cnt.CS2_SERVICE_TYPE))

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



def parseLabel(label_part):
    if not '=' in label_part:
        raise PayloadError('No = in urn label part (%s)' % label_part)

    label_short_type, label_value = label_part.split('=')
    try:
        label_type = LABEL_MAP[label_short_type]
    except KeyError:
        raise PayloadError('Label type %s not recognized')

    return nsa.Label(label_type, label_value)


def findPrefix(network, port):
    prefix = ''
    for x,y in zip(network, port):
        if x == y:
            prefix += x
        else:
            break
    return prefix


def createSTP(stp_id):

    if not stp_id.startswith(URN_NETWORK):
        raise error.PayloadError('STP Id (%s) did not start with %s' % (stp_id, URN_NETWORK))

    tsi = stp_id.replace(URN_NETWORK, '')

    if '?' in tsi:
        loc, lbp = tsi.split('?')
        label = parseLabel(lbp)
    else:
        loc = tsi
        label = None

    if not ':' in loc:
        raise error.PayloadError('No : in stp urn (%s)' % loc)

    network, port_short = loc.rsplit(':', 1)

    # HACK ON!
    base, _ = network.split(':',1)
    port = base + ':' + port_short

    return nsa.STP(network, port, label)



def createSTPID(stp):

    label = ''
    if stp.label:
        label = '?' + stp.label.type_.split('#')[-1] + '=' + stp.label.labelValue() 

    # HACK ON!
    prefix = findPrefix(stp.network, stp.port)
#    prefix = ''
#    for x,y in zip(stp.network, stp.port):
#        if x == y:
#            prefix += x
#        else:
#            break

    lp = len(prefix)
    stp_id = URN_NETWORK + prefix + stp.network[lp:] + ':' + stp.port[lp:] + label
    return stp_id



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

            if rc.serviceDefinition is None:
                log.msg('Did not get any service definitions, cannot build query summary result', system=LOG_SYSTEM)
                raise ValueError('Did not get any service definitions, cannot build query summary result')

            if type(rc.serviceDefinition) is p2pservices.P2PServiceBaseType:
                sd = rc.serviceDefinition
                source_stp = createSTP(sd.sourceSTP)
                dest_stp   = createSTP(sd.destSTP)
                service_def = nsa.Point2PointService(source_stp, dest_stp, sd.capacity, sd.directionality, sd.symmetricPath, None)
            else:
                log.msg('Got non p2ps service, cannot build query summary for that', system=LOG_SYSTEM)
                service_def = None

            crit = nsa.Criteria(int(rc.version), schedule, service_def)
            criterias.append(crit)

    reservation = ( qc.connectionId, qc.globalReservationId, qc.description, criterias, qc.requesterNSA, states, qc.notificationId)
    return reservation



def buildQuerySummaryResultType(reservations):

    def buildServiceDefinition(service_def):
        if type(service_def) is nsa.Point2PointService:
            service_type = cnt.P2P_SERVICE
            sd = service_def
            src_stp_id  = createSTPID(sd.source_stp)
            dst_stp_id  = createSTPID(sd.dest_stp)
            p2ps = p2pservices.P2PServiceBaseType(sd.capacity, sd.directionality, sd.symmetric, src_stp_id, dst_stp_id, None, [])
            return str(p2pservices.p2ps), p2ps
        else:
            return 'N/A', None


    query_results = []

    for rsv in reservations:

        cid, gid, desc, crits, req_nsa, states, nid = rsv
        rsm, psm, lsm, dsm = states

        criterias = []
        for crit in crits:
            schedule = nsiconnection.ScheduleType(createXMLTime(crit.schedule.start_time), createXMLTime(crit.schedule.end_time))
            service_type, service_def = buildServiceDefinition(crit.service_def)
            children = []
            criteria = nsiconnection.QuerySummaryResultCriteriaType(crit.revision, schedule, service_type, children, service_def)
            criterias.append(criteria)

        data_plane_status = nsiconnection.DataPlaneStatusType(dsm[0], dsm[1], dsm[2])
        connection_states = nsiconnection.ConnectionStatesType(rsm, psm, lsm, data_plane_status)

        result_id = 0 # FIXME
        qsrt = nsiconnection.QuerySummaryResultType(cid, gid, desc, criterias, req_nsa, connection_states, nid, result_id)
        query_results.append(qsrt)

    return query_results

