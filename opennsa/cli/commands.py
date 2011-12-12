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
    print "Reservation created at %s Connection ID: %s" % (provider_nsa, connection_id)


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
def querysummary():

    pass


@defer.inlineCallbacks
def querydetails():

    raise NotImplementedError('QueryDetails command not implemented')

