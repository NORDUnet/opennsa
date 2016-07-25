"""
Various query helper functions for nsi2 protocol stack.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012-14)
"""

from twisted.python import log

from opennsa import constants as cnt, nsa
from opennsa.shared.xmlhelper import createXMLTime, parseXMLTimestamp
from opennsa.protocols.nsi2 import helper
from opennsa.protocols.nsi2.bindings import nsiconnection, p2pservices


LOG_SYSTEM = 'NSI2.queryhelper'



## ( nsa native -> xsd )

def buildServiceDefinitionType(service_def):
    if type(service_def) is nsa.Point2PointService:
        sd = service_def
        p2ps = p2pservices.P2PServiceBaseType(sd.capacity, sd.directionality, sd.symmetric, sd.source_stp.urn(), sd.dest_stp.urn(), None, [])
        return p2ps
    else:
        log.msg('Cannot build query service definition for %s (not P2PService)' % str(service_def), system=LOG_SYSTEM)
        return None


def buildConnectionStatesType(states):
    rsm, psm, lsm, dsm = states
    data_plane_status = nsiconnection.DataPlaneStatusType(dsm[0], dsm[1], dsm[2])
    connection_states = nsiconnection.ConnectionStatesType(rsm, psm, lsm, data_plane_status)
    return connection_states


def buildQuerySummaryResultType(connection_infos):

    query_results = []
    for ci in connection_infos:

        criterias = []
        for crit in ci.criterias:
            sched_start_time = createXMLTime(crit.schedule.start_time) if crit.schedule.start_time is not None else None
            sched_end_time   = createXMLTime(crit.schedule.end_time)   if crit.schedule.end_time   is not None else None
            schedule = nsiconnection.ScheduleType(sched_start_time, sched_end_time)
            #service_type = cnt.EVTS_AGOLE
            service_type = str(p2pservices.p2ps) # we need this to have the bindings working properly
            service_def = buildServiceDefinitionType(crit.service_def)
            children = []
            criteria = nsiconnection.QuerySummaryResultCriteriaType(crit.revision, schedule, service_type, children, service_def)
            criterias.append(criteria)

        connection_states = buildConnectionStatesType(ci.states)

        qsrt = nsiconnection.QuerySummaryResultType(ci.connection_id, ci.global_reservation_id, ci.description, criterias,
                                                    ci.requester_nsa, connection_states, ci.notification_id, ci.result_id)
        query_results.append(qsrt)

    return query_results




def buildQueryRecursiveResultType(reservations):

    def buildQueryRecursiveResultCriteriaType(criteria):
        assert type(criteria) is nsa.QueryCriteria, 'Wrong criteria type for buildQueryRecursiveResultCriteriaType: %s' % (str(criteria))

        schedule = nsiconnection.ScheduleType(createXMLTime(criteria.schedule.start_time), createXMLTime(criteria.schedule.end_time))
        #service_type, service_def = buildServiceDefinition(criteria.service_def)
        service_type = str(p2pservices.p2ps) # we need this to have the bindings working properly
        service_def = buildServiceDefinitionType(criteria.service_def)

        crts = []
        for idx, child in enumerate(criteria.children):
            assert type(child) is nsa.ConnectionInfo, 'Invalid child criteria type for buildQueryRecursiveResultCriteriaType: %s' % str(type(child))

            sub_states = buildConnectionStatesType(child.states)
            sub_qrrct = [ buildQueryRecursiveResultCriteriaType( sc ) for sc in child.criterias ]
            crt = nsiconnection.ChildRecursiveType(idx, child.connection_id, child.provider_nsa, sub_states, sub_qrrct)
            crts.append(crt)

        qrrct = nsiconnection.QueryRecursiveResultCriteriaType(criteria.revision, schedule, service_type, crts, service_def)
        return qrrct


    query_results = []

    for ci in reservations:

        criterias = [ buildQueryRecursiveResultCriteriaType(c) for c in ci.criterias ]
        connection_states = buildConnectionStatesType(ci.states)

        qsrt = nsiconnection.QuerySummaryResultType(ci.connection_id, ci.global_reservation_id, ci.description, criterias,
                                                    ci.requester_nsa, connection_states, ci.notification_id, ci.result_id)
        query_results.append(qsrt)


    return query_results



## ( xsd -> nsa native )

def buildSchedule(schedule):

    start_time = parseXMLTimestamp(schedule.startTime) if schedule.startTime is not None else None
    end_time   = parseXMLTimestamp(schedule.endTime)
    return nsa.Schedule(start_time, end_time)


def buildServiceDefinition(service_definition):

    if service_definition is None:
        log.msg('Did not get any service definitions, cannot build service definition', system=LOG_SYSTEM)
        return None

    if type(service_definition) is p2pservices.P2PServiceBaseType:
        sd         = service_definition
        source_stp = helper.createSTP(sd.sourceSTP)
        dest_stp   = helper.createSTP(sd.destSTP)
        return nsa.Point2PointService(source_stp, dest_stp, sd.capacity, sd.directionality, sd.symmetricPath, None)

    else:
        log.msg('Got %s service definition, can only build for P2PService' % str(service_definition), system=LOG_SYSTEM)
        return None


def buildConnectionStates(connection_states):

    r_dps   = connection_states.dataPlaneStatus
    dps     = (r_dps.active, r_dps.version, r_dps.versionConsistent)
    states  = (connection_states.reservationState, connection_states.provisionState, connection_states.lifecycleState, dps)
    return states


def buildCriteria(r_criteria, include_children=False):

    schedule = buildSchedule(r_criteria.schedule)
    service_def = buildServiceDefinition(r_criteria.serviceDefinition)

    children = []
    if include_children:
        for r_child in sorted(r_criteria.children, key=lambda c : c.order):
            # print 'child', r_child.connectionId, r_child.providerNSA, len(r_child.criteria), [ c.children for c in r_child.criteria ]
            crit = r_child.criteria[0] # we only use this for service type, so should be ok
            c_crits = [ buildCriteria(rc, include_children) for rc in r_child.criteria ]
            states = buildConnectionStates(r_child.connectionStates)
            ci = nsa.ConnectionInfo(r_child.connectionId, None, None, crit.serviceType, c_crits, r_child.providerNSA, None, states, None, None)
            children.append( ci )

    crit = nsa.QueryCriteria(int(r_criteria.version), schedule, service_def, children)
    return crit



def buildQueryResult(query_confirmed, provider_nsa, include_children=False):

    qc = query_confirmed

    states = buildConnectionStates(query_confirmed.connectionStates)

    criterias = []
    if qc.criteria is not None:
        for rc in qc.criteria:
            crit = buildCriteria(rc, include_children)
            criterias.append(crit)

    return nsa.ConnectionInfo(qc.connectionId, qc.globalReservationId, qc.description, cnt.EVTS_AGOLE, criterias, provider_nsa, qc.requesterNSA, states, qc.notificationId, qc.resultId)

