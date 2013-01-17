# cli commands

from twisted.python import log
from twisted.internet import defer

from opennsa import nsa, error



# this parser should perhaps be somewhere else
def _createSTP(stp_desc, directionality):
    network, local_part = stp_desc.rsplit(':',1)
    if '#' in local_part:
        port, label_part = local_part.split('#',1)
        labels = []
        for tvl in label_part.split(';'):
            if not '=' in tvl:
                raise ValueError('Invalid label type-value: %s' % tvl)
            type_, values = tvl.split('=')
            labels.append( nsa.Label( type_, values ) )
    else:
        port = local_part
        labels = None

    return nsa.STP(network, port, directionality, labels)


def _createServiceParams(start_time, end_time, src, dst, bandwidth):

    src_stp = _createSTP(src, nsa.EGRESS)
    dst_stp = _createSTP(dst, nsa.INGRESS)

    return nsa.ServiceParameters(start_time, end_time, src_stp, dst_stp, bandwidth)


@defer.inlineCallbacks
def discover(client, service_url):

    res = yield client.queryNSA(service_url)
    print "-- COMMAND RESULT --"
    print res
    print "--"


@defer.inlineCallbacks
def reserve(client, client_nsa, provider_nsa, src, dst, start_time, end_time, bandwidth, connection_id, global_id):

    service_params = _createServiceParams(start_time, end_time, src, dst, bandwidth)

    log.msg("Connection id: %s  Global id: %s" % (connection_id, global_id))

    try:
        yield client.reserve(client_nsa, provider_nsa, None, global_id, 'Test Connection', connection_id, service_params)
        log.msg("Reservation created at %s" % provider_nsa)
    except error.NSIError, e:
        log.msg('Error reserving %s, %s : %s' % (connection_id, e.__class__.__name__, str(e)))



@defer.inlineCallbacks
def reserveprovision(client, client_nsa, provider_nsa, src, dst, start_time, end_time, bandwidth, connection_id, global_id):

    service_params = _createServiceParams(start_time, end_time, src, dst, bandwidth)

    log.msg("Connection id: %s  Global id: %s" % (connection_id, global_id))

    try:
        yield client.reserve(client_nsa, provider_nsa, None, global_id, 'Test Connection', connection_id, service_params)
        log.msg("Connection reserved at %s" % provider_nsa)
    except error.NSIError, e:
        log.msg('Error reserving %s, %s : %s' % (connection_id, e.__class__.__name__, str(e)))
        defer.returnValue(None)

    try:
        yield client.provision(client_nsa, provider_nsa, None, connection_id)
        log.msg('Connection %s provisioned' % connection_id)
    except error.NSIError, e:
        log.msg('Error provisioning %s, %s : %s' % (connection_id, e.__class__.__name__, str(e)))


@defer.inlineCallbacks
def rprt(client, client_nsa, provider_nsa, src, dst, start_time, end_time, bandwidth, connection_id, global_id):
    # reserve, provision, release,  terminate
    service_params = _createServiceParams(start_time, end_time, src, dst, bandwidth)

    log.msg("Connection id: %s  Global id: %s" % (connection_id, global_id))

    try:
        yield client.reserve(client_nsa, provider_nsa, None, global_id, 'Test Connection', connection_id, service_params)
        log.msg("Connection reserved at %s" % provider_nsa)
    except error.NSIError, e:
        log.msg('Error reserving %s, %s : %s' % (connection_id, e.__class__.__name__, str(e)))
        defer.returnValue(None)

    try:
        yield client.provision(client_nsa, provider_nsa, None, connection_id)
        log.msg('Connection %s provisioned' % connection_id)
    except error.NSIError, e:
        log.msg('Error provisioning %s, %s : %s' % (connection_id, e.__class__.__name__, str(e)))

    try:
        yield client.release(client_nsa, provider_nsa, None, connection_id)
        log.msg('Connection %s released' % connection_id)
    except error.NSIError, e:
        log.msg('Error releasing %s, %s : %s' % (connection_id, e.__class__.__name__, str(e)))

    try:
        yield client.terminate(client_nsa, provider_nsa, None, connection_id)
        log.msg('Connection %s terminated' % connection_id)
    except error.NSIError, e:
        log.msg('Error terminating %s, %s : %s' % (connection_id, e.__class__.__name__, str(e)))


@defer.inlineCallbacks
def provision(client, client_nsa, provider_nsa, connection_id):

    try:
        yield client.provision(client_nsa, provider_nsa, None, connection_id)
        log.msg('Connection %s provisioned' % connection_id)
    except error.NSIError, e:
        log.msg('Error provisioning %s, %s : %s' % (connection_id, e.__class__.__name__, str(e)))


@defer.inlineCallbacks
def release(client, client_nsa, provider_nsa, connection_id):

    try:
        yield client.release(client_nsa, provider_nsa, None, connection_id)
        log.msg('Connection %s released' % connection_id)
    except error.NSIError, e:
        log.msg('Error releasing %s, %s : %s' % (connection_id, e.__class__.__name__, str(e)))


@defer.inlineCallbacks
def terminate(client, client_nsa, provider_nsa, connection_id):

    try:
        yield client.terminate(client_nsa, provider_nsa, None, connection_id)
        log.msg('Connection %s terminated' % connection_id)
    except error.NSIError, e:
        log.msg('Error terminating %s, %s : %s' % (connection_id, e.__class__.__name__, str(e)))

@defer.inlineCallbacks
def querysummary(client, client_nsa, provider_nsa, connection_ids, global_reservation_ids):

    try:
        qc = yield client.query(client_nsa, provider_nsa, None, "Summary", connection_ids, global_reservation_ids)
        log.msg('Query results:')
        for qr in qc:
            log.msg('Connection    : %s' % qr.connectionId)
            if qr.globalReservationId:
                log.msg('  Global ID   : %s' % qr.globalReservationId)
            if qr.description:
                log.msg('  Description : %s' % qr.description)

            log.msg('  Reservation state : %s' % qr.connectionStates.reservationState.state)
            log.msg('  Provision   state : %s' % qr.connectionStates.provisionState.state)
            log.msg('  Activaction state : %s' % qr.connectionStates.activationState.state)
            if qr.children:
                log.msg('  Children    : %s' % qr.children)
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

