# cli commands

from twisted.python import log, usage
from twisted.internet import defer

from opennsa import constants as cnt, nsa, error
from opennsa.protocols.nsi2.bindings import p2pservices

LABEL_MAP = {
    'vlan' : cnt.ETHERNET_VLAN,
    'mpls' : cnt.MPLS
}


def _createSTP(stp_arg):

    if not ':' in stp_arg:
        raise usage.UsageError('No ":" in stp, invalid format (see docs/cli.md)')

    if '#' in stp_arg:
        stp_desc, label_desc = stp_arg.split('#')
        network, port = stp_desc.rsplit(':',1)
        if not '=' in label_desc:
            raise usage.UsageError('No "=" in stp label, invalid format (see docs/cli.md)')
        label_type,label_value = label_desc.split("=")
        label = nsa.Label(LABEL_MAP[label_type],label_value) # FIXME need good error message if label type doesn't exist
    else:
        network, port = stp_arg.rsplit(':',1)
        label = None

    return nsa.STP(network, port, label)

# Take a string of ERO STP and convert to a list of OrderedStpType.
def _createOrderedStpType(ero):
    if ero is None:
        return None

    ero_list = [x.strip() for x in ero.split(',')]
    order = 0
    ordered_stp = []
    for item in ero_list:
        ordered_stp.append(p2pservices.OrderedStpType(order, _createSTP(item).urn()))
        order += 1

    return ordered_stp


def _createP2PS(src, dst, capacity, ero):

    src_stp = _createSTP(src)
    dst_stp = _createSTP(dst)
    ordered_stp = _createOrderedStpType(ero)

    return nsa.Point2PointService(src_stp, dst_stp, capacity, cnt.BIDIRECTIONAL, False, ordered_stp, None)


def _handleEvent(event):

    notification_type, header, entry = event

    if notification_type == 'errorEvent':
        log.msg('Error event: %s' % str(entry))
        return True
    elif notification_type == 'dataPlaneStateChange':
        cid, nid, timestamp, dps = entry
        active, version, consistent = dps
        if active:
            log.msg('Connection %s Data plane active, version %i, consistent: %s' % (cid, version, consistent))
            return False
        else:
            log.msg('Connection %s Data plane down, version %i, consistent: %s' % (cid, version, consistent))
            return consistent # this means we don't exit on initial partially down, where we are not consistent

    else:
        log.msg('Unrecognized event %s ' % notification_type)
        return False


def _logError(e):
    # emit the error to the user

    error_type = e.__class__.__name__

    log.msg('%s from %s' % (error_type, e.nsaId))
    log.msg('  %s' % e)
    if e.variables:
        log.msg('Variables: %s' % ' '.join ( [ ': '.join(tvp) for tvp in e.variables ] ) )



@defer.inlineCallbacks
def discover(client, service_url):

    res = yield client.queryNSA(service_url)
    print "-- COMMAND RESULT --"
    print res
    print "--"


@defer.inlineCallbacks
def reserveonly(client, nsi_header, src, dst, start_time, end_time, capacity, ero, connection_id, global_id):

    schedule = nsa.Schedule(start_time, end_time)
    service_def = _createP2PS(src, dst, capacity, ero)
    crt = nsa.Criteria(0, schedule, service_def)

    try:
        nsi_header.connection_trace = [ nsi_header.requester_nsa + ':' + '1' ]
        connection_id, _,_,criteria  = yield client.reserve(nsi_header, connection_id, global_id, 'Test Connection', crt)
        nsi_header.connection_trace = None
        sd = criteria.service_def
        log.msg("Connection created and held. Id %s at %s" % (connection_id, nsi_header.provider_nsa))
        log.msg("Source - Destination: %s - %s" % (sd.source_stp, sd.dest_stp))

    except error.NSIError, e:
        _logError(e)


@defer.inlineCallbacks
def reserve(client, nsi_header, src, dst, start_time, end_time, capacity, ero, connection_id, global_id):

    schedule = nsa.Schedule(start_time, end_time)
    service_def = _createP2PS(src, dst, capacity, ero)
    crt = nsa.Criteria(0, schedule, service_def)

    try:
        nsi_header.connection_trace = [ nsi_header.requester_nsa + ':' + '1' ]
        connection_id, global_reservation_id, description, criteria = yield client.reserve(nsi_header, connection_id, global_id, 'Test Connection', crt)
        nsi_header.connection_trace = None
        sd = criteria.service_def
        log.msg("Connection created and held. Id %s at %s" % (connection_id, nsi_header.provider_nsa))
        log.msg("Source - Destination: %s - %s" % (sd.source_stp, sd.dest_stp))

        nsi_header.newCorrelationId()
        yield client.reserveCommit(nsi_header, connection_id)
        log.msg("Reservation committed at %s" % nsi_header.provider_nsa)

    except error.NSIError, e:
        _logError(e)


@defer.inlineCallbacks
def reserveprovision(client, nsi_header, src, dst, start_time, end_time, capacity, ero, connection_id, global_id, notification_wait):

    schedule = nsa.Schedule(start_time, end_time)
    service_def = _createP2PS(src, dst, capacity, ero)
    crt = nsa.Criteria(0, schedule, service_def)

    try:
        nsi_header.connection_trace = [ nsi_header.requester_nsa + ':' + '1' ]
        connection_id, _,_, criteria = yield client.reserve(nsi_header, connection_id, global_id, 'Test Connection', crt)
        nsi_header.connection_trace = []
        sd = criteria.service_def
        log.msg("Connection created and held. Id %s at %s" % (connection_id, nsi_header.provider_nsa))
        log.msg("Source - Destination: %s - %s" % (sd.source_stp, sd.dest_stp))

        nsi_header.newCorrelationId()
        yield client.reserveCommit(nsi_header, connection_id)
        log.msg("Connection committed at %s" % nsi_header.provider_nsa)

        # query
        nsi_header.newCorrelationId()
        qr = yield client.querySummary(nsi_header, connection_ids=[connection_id] )
        print "Query result:", qr

        # provision
        nsi_header.newCorrelationId()
        yield client.provision(nsi_header, connection_id)
        log.msg('Connection %s provisioned' % connection_id)

        while notification_wait:
            event = yield client.notifications.get()
            exit = _handleEvent(event)
            if exit:
                break

    except error.NSIError, e:
        _logError(e)



@defer.inlineCallbacks
def rprt(client, nsi_header, src, dst, start_time, end_time, capacity, ero, connection_id, global_id):
    # reserve, provision, release,  terminate
    schedule = nsa.Schedule(start_time, end_time)
    service_def = _createP2PS(src, dst, capacity, ero)
    crt = nsa.Criteria(0, schedule, service_def)

    try:
        nsi_header.connection_trace = [ nsi_header.requester_nsa + ':' + '1' ]
        connection_id, _,_, criteria = yield client.reserve(nsi_header, connection_id, global_id, 'Test Connection', crt)
        nsi_header.connection_trace = []
        sd = criteria.service_def
        log.msg("Connection created and held. Id %s at %s" % (connection_id, nsi_header.provider_nsa))
        log.msg("Source - Destination: %s - %s" % (sd.source_stp, sd.dest_stp))

        # commit
        nsi_header.newCorrelationId()
        yield client.reserveCommit(nsi_header, connection_id)
        log.msg("Connection committed at %s" % nsi_header.provider_nsa)

        # provision
        nsi_header.newCorrelationId()
        yield client.provision(nsi_header, connection_id)
        log.msg('Connection %s provisioned' % connection_id)

        # release
        nsi_header.newCorrelationId()
        yield client.release(nsi_header, connection_id)
        log.msg('Connection %s released' % connection_id)

        # terminate
        nsi_header.newCorrelationId()
        yield client.terminate(nsi_header, connection_id)
        log.msg('Connection %s terminated' % connection_id)

    except error.NSIError, e:
        _logError(e)


@defer.inlineCallbacks
def reservecommit(client, nsi_header, connection_id):

    try:
        yield client.reserveCommit(nsi_header, connection_id)
        log.msg("Reservation committed at %s" % nsi_header.provider_nsa)

    except error.NSIError, e:
        _logError(e)


@defer.inlineCallbacks
def provision(client, nsi_header, connection_id, notification_wait):

    try:
        yield client.provision(nsi_header, connection_id)
        log.msg('Connection %s provisioned' % connection_id)
    except error.NSIError, e:
        _logError(e)

    if notification_wait:
        log.msg("Notification wait not added to provision yet")


@defer.inlineCallbacks
def release(client, nsi_header, connection_id, notification_wait):

    try:
        yield client.release(nsi_header, connection_id)
        log.msg('Connection %s released' % connection_id)
    except error.NSIError, e:
        _logError(e)

    if notification_wait:
        log.msg("Notification wait not added to release yet")


@defer.inlineCallbacks
def terminate(client, nsi_header, connection_id):

    try:
        yield client.terminate(nsi_header, connection_id)
        log.msg('Connection %s terminated' % connection_id)
    except error.NSIError, e:
        _logError(e)




def _emitQueryResult(query_result, i='', child=False):

    qr = query_result

    log.msg('')
    log.msg(i + 'Connection   %s (%s)' % (qr.connection_id, qr.provider_nsa) )
    if qr.global_reservation_id:
        log.msg(i + 'Global ID    %s' % qr.global_reservation_id)
    if qr.description:
        log.msg(i + 'Description  %s' % qr.description)

    states = qr.states
    dps = states[3]
    log.msg(i + 'States       %s' % ', '.join(states[0:3]))
    log.msg(i + 'Dataplane    Active : %s, Version: %s, Consistent %s' % dps)

    if qr.criterias:
        crit = qr.criterias[0]
        if not child:
            log.msg(i + 'Start-End    %s - %s' % (crit.schedule.start_time, crit.schedule.end_time))
        if type(crit.service_def) is nsa.Point2PointService:
            sd = crit.service_def
            #log.msg(i + 'Source      : %s' % sd.source_stp.shortName())
            #log.msg(i + 'Destination : %s' % sd.dest_stp.shortName())
            log.msg(i + 'Path         %s -- %s' % (sd.source_stp.shortName(), sd.dest_stp.shortName()) )
            if not child: # these should be the same everywhere
                log.msg(i + 'Bandwidth    %s' % sd.capacity)
                log.msg(i + 'Direction    %s' % sd.directionality)
                if sd.symmetric: # only show symmetric if set
                    log.msg(i + 'Symmetric    %s' % sd.symmetric)
                if sd.parameters:
                    log.msg(i + 'Params       %s' % sd.parameters)
        else:
            log.msg(i + 'Unrecognized service definition: %s' % str(crit.service_def))

        for c in crit.children:
            _emitQueryResult(c, i + '  ', True)




@defer.inlineCallbacks
def querySummary(client, nsi_header, connection_ids, global_reservation_ids):

    try:
        qc = yield client.querySummary(nsi_header, connection_ids, global_reservation_ids)
        if not qc:
            log.msg('No results from query')
            defer.returnValue(None)

        log.msg('Query results:')
        for qr in qc:
            _emitQueryResult(qr)
        log.msg('')

    except error.NSIError, e:
        _logError(e)


@defer.inlineCallbacks
def queryRecursive(client, nsi_header, connection_ids, global_reservation_ids):

    try:
        qc = yield client.queryRecursive(nsi_header, connection_ids, global_reservation_ids)
        if not qc:
            log.msg('No results from query')
            defer.returnValue(None)

        log.msg('Query results:')
        for qr in qc:
            _emitQueryResult(qr)
        log.msg('')

    except error.NSIError, e:
        _logError(e)

