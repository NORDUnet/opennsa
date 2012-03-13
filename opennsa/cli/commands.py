# cli commands

from twisted.python import log
from twisted.internet import defer

from opennsa import nsa



@defer.inlineCallbacks
def reserve(client, client_nsa, provider_nsa, source_stp, dest_stp, start_time, end_time, bandwidth, connection_id, global_id):

    source_network, source_port = source_stp.split(':',1)
    dest_network,   dest_port   = dest_stp.split(':', 1)

    r_source_stp    = nsa.STP(source_network, source_port)
    r_dest_stp      = nsa.STP(dest_network,   dest_port)

    bwp = nsa.BandwidthParameters(bandwidth)
    service_params  = nsa.ServiceParameters(start_time, end_time, r_source_stp, r_dest_stp, bandwidth=bwp)

    log.msg("Connection ID: %s" % connection_id)
    log.msg("Global ID: %s" % global_id)

    _ = yield client.reserve(client_nsa, provider_nsa, None, global_id, 'Test Connection', connection_id, service_params)
    print "Reservation created at %s" % provider_nsa


@defer.inlineCallbacks
def provision(client, client_nsa, provider_nsa, connection_id):

    _ = yield client.provision(client_nsa, provider_nsa, None, connection_id)
    log.msg('Connection %s provisioned' % connection_id)


@defer.inlineCallbacks
def release(client, client_nsa, provider_nsa, connection_id):

    _ = yield client.release(client_nsa, provider_nsa, None, connection_id)
    log.msg('Connection %s released' % connection_id)


@defer.inlineCallbacks
def terminate(client, client_nsa, provider_nsa, connection_id):

    _ = yield client.terminate(client_nsa, provider_nsa, None, connection_id)
    log.msg('Connection %s terminated' % connection_id)


@defer.inlineCallbacks
def querysummary(client, client_nsa, provider_nsa, connection_ids, global_reservation_ids):

    qc = yield client.query(client_nsa, provider_nsa, None, "Summary", connection_ids, global_reservation_ids)
    log.msg('Query results:')
    log.msg( str(qc) )


@defer.inlineCallbacks
def querydetails(client, client_nsa, provider_nsa, connection_ids, global_reservation_ids):

    qc = yield client.query(client_nsa, provider_nsa, None, "Details", connection_ids, global_reservation_ids)
    log.msg('Query results:')
    log.msg( str(qc) )


def path(topology_file, source_stp, dest_stp):

    from opennsa import topology

    topo = topology.parseTopology( [ open(topology_file) ] )

    source_network, source_port = source_stp.split(':',1)
    dest_network,   dest_port   = dest_stp.split(':', 1)

    r_source_stp    = nsa.STP(source_network, source_port)
    r_dest_stp      = nsa.STP(dest_network,   dest_port)

    paths = topo.findPaths(r_source_stp, r_dest_stp)

    for p in sorted(paths, key=lambda p : len(p.network_links)):
        log.msg(str(p))


def topology(topology_file):

    from opennsa import topology

    topo = topology.parseTopology( [ open(topology_file) ] )

    for nw in topo.networks:
        ns = '%s (%s)' % (nw.name, ','.join( sorted( [ ep.endpoint for ep in nw.endpoints ] ) ) )
        log.msg(ns)


def topologyGraph(topology_file, all_links=False):

    from opennsa import topology

    topo = topology.parseTopology( [ open(topology_file) ] )

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

