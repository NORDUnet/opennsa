# cli commands

import os
import uuid
import random
import time
import datetime

from twisted.python import log
from twisted.internet import reactor, defer

from opennsa import nsa, setup


# this needs be configurable somehow
HOST = 'localhost'
PORT = 7080


@defer.inlineCallbacks
def reserve(wsdl_dir, service_url, provider_nsa, requester_nsa, source_stp, dest_stp):

    client, service, factory = setup.createClient(HOST, PORT, wsdl_dir)

    reactor.listenTCP(PORT, factory)

    requester_url = 'http://%s:%i/NSI/services/ConnectionService' % (HOST, PORT)

    client_nsa  = nsa.NetworkServiceAgent(requester_nsa, requester_url)
    provider    = nsa.Network('Do we need this?', nsa.NetworkServiceAgent(provider_nsa, service_url))

    source_network, source_port = source_stp.split(':',1)
    dest_network, dest_port     = dest_stp.split(':', 1)

    r_source_stp    = nsa.STP(source_network, source_port)
    r_dest_stp      = nsa.STP(dest_network,   dest_port)

    # all this needs to be settable
    start_time = datetime.datetime.utcfromtimestamp(time.time() + 2 )
    end_time   = datetime.datetime.utcfromtimestamp(time.time() + 60 )
    bwp = nsa.BandwidthParameters(1000)
    service_params  = nsa.ServiceParameters(start_time, end_time, r_source_stp, r_dest_stp, bandwidth=bwp)
    global_id       = 'urn:uuid:' + str(uuid.uuid1())
    connection_id   = 'conn-%i' % random.randrange(1000,9999)

    print "Connection ID", connection_id
    print "Global ID", global_id

    r = yield client.reserve(client_nsa, provider.nsa, None, global_id, 'Test Connection', connection_id, service_params)
    print "Reservation created. Connection ID:", connection_id

