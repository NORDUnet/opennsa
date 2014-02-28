# cli commands

from twisted.python import log
from twisted.internet import defer

from opennsa import constants as cnt, nsa, error



def _createSTP(stp_arg):

    # no generic label stuff for now
    if '#' in stp_arg:
        stp_desc, vlan = stp_arg.split('#')
        network, port = stp_desc.rsplit(':',1)
        label = nsa.Label(cnt.ETHERNET_VLAN, vlan)
    else:
        network, port = stp_arg.rsplit(':',1)
        label = None

    return nsa.STP(network, port, label)


def _createP2PS(src, dst, capacity):

    src_stp = _createSTP(src)
    dst_stp = _createSTP(dst)

    return nsa.Point2PointService(src_stp, dst_stp, capacity)


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


@defer.inlineCallbacks
def discover(client, service_url):

    res = yield client.queryNSA(service_url)
    print "-- COMMAND RESULT --"
    print res
    print "--"


@defer.inlineCallbacks
def reserveonly(client, client_nsa, provider_nsa, src, dst, start_time, end_time, capacity, connection_id, global_id):

    nsi_header = nsa.NSIHeader(client_nsa.urn(), provider_nsa.urn(), reply_to=provider_nsa.endpoint)
    schedule = nsa.Schedule(start_time, end_time)
    service_def = _createP2PS(src, dst, capacity)
    crt = nsa.Criteria(0, schedule, service_def)

    if connection_id:
        log.msg("Connection id: %s  Global id: %s" % (connection_id, global_id))

    try:
        assigned_connection_id = yield client.reserve(nsi_header, connection_id, global_id, 'Test Connection', crt)
        log.msg("Connection created and held. Id %s at %s" % (assigned_connection_id, provider_nsa))

    except error.NSIError, e:
        log.msg('Error reserving, %s: %s' % (e.__class__.__name__, str(e)))


@defer.inlineCallbacks
def reserve(client, client_nsa, provider_nsa, src, dst, start_time, end_time, capacity, connection_id, global_id):

    nsi_header = nsa.NSIHeader(client_nsa.urn(), provider_nsa.urn(), reply_to=provider_nsa.endpoint)
    schedule = nsa.Schedule(start_time, end_time)
    service_def = _createP2PS(src, dst, capacity)
    crt = nsa.Criteria(0, schedule, service_def)

    if connection_id or global_id:
        log.msg("Connection id: %s  Global id: %s" % (connection_id, global_id))


    try:
        assigned_connection_id = yield client.reserve(nsi_header, connection_id, global_id, 'Test Connection', crt)
        log.msg("Connection created and held. Id %s at %s" % (assigned_connection_id, provider_nsa))
        yield client.reserveCommit(nsi_header, assigned_connection_id)
        log.msg("Reservation committed at %s" % provider_nsa)

    except error.NSIError, e:
        log.msg('Error reserving, %s: %s' % (e.__class__.__name__, str(e)))


@defer.inlineCallbacks
def reserveprovision(client, client_nsa, provider_nsa, src, dst, start_time, end_time, capacity, connection_id, global_id, notification_wait):

    nsi_header = nsa.NSIHeader(client_nsa.urn(), provider_nsa.urn())
    schedule = nsa.Schedule(start_time, end_time)
    service_def = _createP2PS(src, dst, capacity)
    crt = nsa.Criteria(0, schedule, service_def)

    log.msg("Connection id: %s  Global id: %s" % (connection_id, global_id))

    try:
        assigned_connection_id = yield client.reserve(nsi_header, connection_id, global_id, 'Test Connection', crt)
        log.msg("Connection created and held. Id %s at %s" % (assigned_connection_id, provider_nsa))
        nsi_header.newCorrelationId()
        yield client.reserveCommit(nsi_header, assigned_connection_id)
        log.msg("Connection committed at %s" % provider_nsa)
    except error.NSIError, e:
        log.msg('Error reserving, %s : %s' % (e.__class__.__name__, str(e)))
        defer.returnValue(None)

    try:
        nsi_header.newCorrelationId()
        qr = yield client.querySummary(nsi_header, connection_ids=[assigned_connection_id] )
        print "QR", qr
    except error.NSIError, e:
        log.msg('Error querying %s, %s : %s' % (assigned_connection_id, e.__class__.__name__, str(e)))

    try:
        nsi_header.newCorrelationId()
        yield client.provision(nsi_header, assigned_connection_id)
        log.msg('Connection %s provisioned' % assigned_connection_id)
    except error.NSIError, e:
        log.msg('Error provisioning, %s : %s' % (e.__class__.__name__, str(e)))

    while notification_wait:
        event = yield client.notifications.get()
        exit = _handleEvent(event)
        if exit:
            break



@defer.inlineCallbacks
def rprt(client, client_nsa, provider_nsa, src, dst, start_time, end_time, capacity, connection_id, global_id):
    # reserve, provision, release,  terminate
    nsi_header = nsa.NSIHeader(client_nsa.urn(), provider_nsa.urn())
    schedule = nsa.Schedule(start_time, end_time)
    service_def = _createP2PS(src, dst, capacity)
    crt = nsa.Criteria(0, schedule, service_def)

    log.msg("Connection id: %s  Global id: %s" % (connection_id, global_id))

    try:
        assigned_connection_id = yield client.reserve(nsi_header, connection_id, global_id, 'Test Connection', crt)
        log.msg("Connection created and held. Id %s at %s" % (assigned_connection_id, provider_nsa))
        nsi_header.newCorrelationId()
        yield client.reserveCommit(nsi_header, assigned_connection_id)
        log.msg("Connection committed at %s" % provider_nsa)
    except error.NSIError, e:
        log.msg('Error reserving %s, %s : %s' % (connection_id, e.__class__.__name__, str(e)))
        defer.returnValue(None)

    try:
        nsi_header.newCorrelationId()
        yield client.provision(nsi_header, assigned_connection_id)
        log.msg('Connection %s provisioned' % assigned_connection_id)
    except error.NSIError, e:
        log.msg('Error provisioning %s, %s : %s' % (assigned_connection_id, e.__class__.__name__, str(e)))
        defer.returnValue(None)

    try:
        nsi_header.newCorrelationId()
        yield client.release(nsi_header, assigned_connection_id)
        log.msg('Connection %s released' % assigned_connection_id)
    except error.NSIError, e:
        log.msg('Error releasing %s, %s : %s' % (assigned_connection_id, e.__class__.__name__, str(e)))
        defer.returnValue(None)

    try:
        nsi_header.newCorrelationId()
        yield client.terminate(nsi_header, assigned_connection_id)
        log.msg('Connection %s terminated' % assigned_connection_id)
    except error.NSIError, e:
        log.msg('Error terminating %s, %s : %s' % (assigned_connection_id, e.__class__.__name__, str(e)))
        defer.returnValue(None)


@defer.inlineCallbacks
def reservecommit(client, client_nsa, provider_nsa, connection_id):

    nsi_header = nsa.NSIHeader(client_nsa.urn(), provider_nsa.urn(), reply_to=provider_nsa.endpoint)

    log.msg("Connection id: %s" % connection_id)

    try:
        yield client.reserveCommit(nsi_header, connection_id)
        log.msg("Reservation committed at %s" % provider_nsa)

    except error.NSIError, e:
        log.msg('Error comitting, %s: %s' % (e.__class__.__name__, str(e)))


@defer.inlineCallbacks
def provision(client, client_nsa, provider_nsa, connection_id, notification_wait):

    nsi_header = nsa.NSIHeader(client_nsa.urn(), provider_nsa.urn(), reply_to=provider_nsa.endpoint)

    try:
        yield client.provision(nsi_header, connection_id)
        log.msg('Connection %s provisioned' % connection_id)
    except error.NSIError, e:
        log.msg('Error provisioning %s, %s : %s' % (connection_id, e.__class__.__name__, str(e)))

    if notification_wait:
        log.msg("Notification wait not added to provision yet")


@defer.inlineCallbacks
def release(client, client_nsa, provider_nsa, connection_id, notification_wait):

    header = nsa.NSIHeader(client_nsa.urn(), provider_nsa.urn())
    try:
        yield client.release(header, connection_id)
        log.msg('Connection %s released' % connection_id)
    except error.NSIError, e:
        log.msg('Error releasing %s, %s : %s' % (connection_id, e.__class__.__name__, str(e)))

    if notification_wait:
        log.msg("Notification wait not added to release yet")


@defer.inlineCallbacks
def terminate(client, client_nsa, provider_nsa, connection_id):

    header = nsa.NSIHeader(client_nsa.urn(), provider_nsa.urn())
    try:
        yield client.terminate(header, connection_id)
        log.msg('Connection %s terminated' % connection_id)
    except error.NSIError, e:
        log.msg('Error terminating %s, %s : %s' % (connection_id, e.__class__.__name__, str(e)))

@defer.inlineCallbacks
def querysummary(client, client_nsa, provider_nsa, connection_ids, global_reservation_ids):

    header = nsa.NSIHeader(client_nsa.urn(), provider_nsa.urn())
    try:
        qc = yield client.querySummary(header, connection_ids, global_reservation_ids)
        log.msg('Query results:')
        for qr in qc:
            cid, gid, desc, crits, requester, states, children = qr
            dps = states[3]
            log.msg('Connection    : %s' % cid)
            if gid:
                log.msg('  Global ID   : %s' % gid)
            if desc:
                log.msg('  Description : %s' % desc)

            if crits:
                crit = crits[0]
                log.msg('  Start time  : %s, End time: %s' % (crit.start_time, crit.end_time))
                log.msg('  Source STP  : %s' % crit.source_stp)
                log.msg('  Dest   STP  : %s' % crit.dest_stp)
                log.msg('  Bandwidth   : %s' % crit.bandwidth)

            log.msg('  States      : %s' % ', '.join(states[0:3]))
            log.msg('  Dataplane   : Active : %s, Version: %s, Consistent %s' % dps)

            if children:
                log.msg('  Children    : %s' % children)
    except error.NSIError, e:
        log.msg('Error querying %s, %s : %s' % (connection_ids, e.__class__.__name__, str(e)))


@defer.inlineCallbacks
def querydetails(client, client_nsa, provider_nsa, connection_ids, global_reservation_ids):

    try:
        qc = yield client.query(client_nsa, provider_nsa, None, "Details", connection_ids, global_reservation_ids)
        log.msg('Query results:')
        for qr in qc:
            log.msg('Connection: %s' % qr.connectionId)
            log.msg('  States: %s' % qr.connectionStates)
    except error.NSIError, e:
        log.msg('Error querying %s, %s : %s' % (connection_ids, e.__class__.__name__, str(e)))


def path(topology_file, source_stp, dest_stp):

    raise NotImplementedError('Path computation not available for NML yet')
    topo = None

    source_network, source_port = source_stp.split(':',1)
    dest_network,   dest_port   = dest_stp.split(':', 1)

    r_source_stp    = nsa.STP(source_network, source_port)
    r_dest_stp      = nsa.STP(dest_network,   dest_port)

    paths = topo.findPaths(r_source_stp, r_dest_stp)

    for p in sorted(paths, key=lambda p : len(p.network_links)):
        log.msg(str(p))


def topology(topology_file):

    raise NotImplementedError('Topology dump not available for NML yet')
    topo = None

    for nw in topo.networks:
        ns = '%s (%s)' % (nw.name, ','.join( sorted( [ ep.endpoint for ep in nw.endpoints ] ) ) )
        log.msg(ns)


def topologyGraph(topology_file, all_links=False):

    raise NotImplementedError('Topology graph not available for NML yet')
    topo = None

    links = []

    for nw in topo.networks:
        for ep in nw.endpoints:
            if ep.dest_stp:
                nw1 = nw.name.replace('.ets', '').replace('-','_')
                nw2 = ep.dest_stp.network.replace('.ets', '').replace('-', '_')

                l = [ nw1, nw2 ]
                if all_links:
                    if nw1 < nw2: # this prevents us from building double links
                        links.append(l)
                else:
                    l = sorted(l)
                    if not l in links:
                        links.append(l)

    log.msg('graph Network {')
    for l in sorted(links):
        log.msg('  %s -- %s;' % (l[0], l[1]))
    log.msg('}')

