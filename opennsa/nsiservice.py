"""
OpenNSA NSI Service -> Backend adaptor (router).

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import uuid
import datetime

from zope.interface import implements

from twisted.python import log, failure
from twisted.internet import reactor, defer, task

from opennsa.interface import NSIServiceInterface
from opennsa import nsa, error, registry, subscription, database, state, aggregator



LOG_SYSTEM = 'NSIService'



class NSIService:

    implements(NSIServiceInterface)

    def __init__(self, network, backend, service_registry, topology):
        self.network = network
        self.backend = backend
        self.service_registry = service_registry

        self.topology = topology
        nsa_ = None # Fixme later
        self.aggregator = aggregator.Aggregator(network, nsa_, topology, service_registry)

        self.service_registry.registerEventHandler(registry.RESERVE,   self.reserve,   registry.SYSTEM_SERVICE)
        self.service_registry.registerEventHandler(registry.PROVISION, self.provision, registry.SYSTEM_SERVICE)
        self.service_registry.registerEventHandler(registry.RELEASE,   self.release,   registry.SYSTEM_SERVICE)
        self.service_registry.registerEventHandler(registry.TERMINATE, self.terminate, registry.SYSTEM_SERVICE)
        self.service_registry.registerEventHandler(registry.QUERY,     self.query,     registry.SYSTEM_SERVICE)


    # utility functionality

    def getConnection(self, requester_nsa, connection_id):

        def gotResult(connections):
            # we should get 0 or 1 here since connection id is unique
            if len(connections) == 0:
                return defer.fail( error.ConnectionNonExistentError('No connection with id %s' % connection_id) )
            return connections[0]

        d = database.ServiceConnection.findBy(connection_id=connection_id)
        d.addCallback(gotResult)
        return d


    # command functionality

    @defer.inlineCallbacks
    def reserve(self, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters, sub):

        log.msg('', system=LOG_SYSTEM)
        log.msg('Reserve request. NSA: %s. Connection ID: %s' % (requester_nsa, connection_id), system=LOG_SYSTEM)

        # rethink with modify...
        connection_exists = yield database.ServiceConnection.exists(['connection_id = ?', connection_id])
        if connection_exists:
            raise error.ConnectionExistsError('Connection with id %s already exists' % connection_id)

        source_stp = service_parameters.source_stp
        dest_stp   = service_parameters.dest_stp

        # check that we know the networks
        self.topology.getNetwork(source_stp.network)
        self.topology.getNetwork(dest_stp.network)

        # if the link terminates at our network, ensure that ports exists
        if source_stp.network == self.network:
            source_port = self.topology.getNetwork(self.network).getPort(source_stp.port)
        if dest_stp.network == self.network:
            dest_port = self.topology.getNetwork(self.network).getPort(dest_stp.port)

        if source_stp == dest_stp and source_stp.label.singleValue():
            raise error.TopologyError('Cannot connect %s to itself.' % source_stp)

        conn = database.ServiceConnection(connection_id=connection_id, revision=0, global_reservation_id=global_reservation_id, description=description, nsa=requester_nsa,
                            reserve_time=datetime.datetime.utcnow(),
                            reservation_state=state.INITIAL, provision_state=state.SCHEDULED, activation_state=state.INACTIVE, lifecycle_state=state.INITIAL,
                            source_network=source_stp.network, source_port=source_stp.port, source_labels=source_stp.labels,
                            dest_network=dest_stp.network, dest_port=dest_stp.port, dest_labels=dest_stp.labels,
                            start_time=service_parameters.start_time, end_time=service_parameters.end_time,
                            bandwidth=service_parameters.bandwidth)
        yield conn.save()

        # since STPs are candidates here, we need to change these later on

        def reserveResponse(result):
            success = False if isinstance(result, failure.Failure) else True
            if not success:
                log.msg('Error reserving: %s' % result.getErrorMessage(), system=LOG_SYSTEM)
            d = subscription.dispatchNotification(success, result, sub, self.service_registry)


        # now reserve connections needed to create path
        d = task.deferLater(reactor, 0, self.aggregator.reserve, conn)
        d.addBoth(reserveResponse)
        yield d


    @defer.inlineCallbacks
    def provision(self, requester_nsa, provider_nsa, session_security_attr, connection_id, sub):

        def provisionResponse(result):
            success = False if isinstance(result, failure.Failure) else True
            if not success:
                log.msg('Error provisioning: %s' % result.getErrorMessage(), system=LOG_SYSTEM)
            d = subscription.dispatchNotification(success, result, sub, self.service_registry)

        log.msg('', system=LOG_SYSTEM)
        # security check here

        conn = yield self.getConnection(requester_nsa, connection_id)
        d = task.deferLater(reactor, 0, self.aggregator.provision, conn)
        d.addBoth(provisionResponse)
        yield d


    @defer.inlineCallbacks
    def release(self, requester_nsa, provider_nsa, session_security_attr, connection_id, sub):

        def releaseResponse(result):
            success = False if isinstance(result, failure.Failure) else True
            if not success:
                log.msg('Error releasing: %s' % result.getErrorMessage(), system=LOG_SYSTEM)
            d = subscription.dispatchNotification(success, result, sub, self.service_registry)

        log.msg('', system=LOG_SYSTEM)
        # security check here

        conn = yield self.getConnection(requester_nsa, connection_id)
        d = task.deferLater(reactor, 0, conn.release)
        d.addBoth(releaseResponse)


    @defer.inlineCallbacks
    def terminate(self, requester_nsa, provider_nsa, session_security_attr, connection_id, sub):

        def terminateResponse(result):
            success = False if isinstance(result, failure.Failure) else True
            if not success:
                log.msg('Error terminating: %s' % result.getErrorMessage(), system=LOG_SYSTEM)
            d = subscription.dispatchNotification(success, result, sub, self.service_registry)

        log.msg('', system=LOG_SYSTEM)
        # security check here

        conn = yield self.getConnection(requester_nsa, connection_id)
        d = task.deferLater(reactor, 0, conn.terminate)
        d.addBoth(terminateResponse)


    def query(self, requester_nsa, provider_nsa, session_security_attr, operation, connection_ids, global_reservation_ids, sub):

        # security check here

        conns = []
        if connection_ids is None and global_reservation_ids is None:
            match = lambda conn : True
        else:
            match = lambda conn : conn.connection_id in connection_ids if connection_ids is not None else False or \
                                  conn.global_reservation_id in global_reservation_ids if global_reservation_ids is not None else False

        # This hack can be removed after SC11
        if requester_nsa == 'urn:ogf:network:nsa:OpenNSA-querier':
            # Be less noisy, query is something that happens fairly often.
            #log.msg('Enabling special demo query support for querier: %s' % (requester_nsa), system=LOG_SYSTEM)
            for connections in self.connections.values():
                for conn in connections.values():
                    if match(conn):
                        conns.append(conn)

        else:
            for conn in self.connections.get(requester_nsa, {}).values():
                if match(conn):
                    conns.append(conn)

        if not sub.match(registry.QUERY_RESPONSE):
            log.msg('Got query request with non-query response subscription')
        else:
            d = subscription.dispatchNotification(True, conns, sub, self.service_registry)

        return defer.succeed(None)

