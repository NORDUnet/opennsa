"""
Generic backend for deployments where OpenNSA is the only NRM (i.e. there is no
other system for interacting with the hardware).

Using this module, such a backend will only have to supply functionality for
setting up and tearing down links and does not have to deal state management.

The use this module a connection manager has to be supplied. The methods
setupLink(source_port, dest_port) and tearDown(source_port, dest_port) must be
implemented in the manager. The methods should return a deferred.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

#import uuid
import random
import datetime

from dateutil.tz import tzutc

from twisted.python import log
from twisted.internet import defer

from opennsa import error, state, nsa, database
from opennsa.backends.common import scheduler

from twistar.dbobject import DBObject



class Simplebackendconnection(DBObject):
    pass



class SimpleBackend:

    def __init__(self, network, connection_manager, log_system):

        self.network = network
        self.connection_manager = connection_manager
        self.log_system = log_system

        self.schedulers = {}

        # need to build schedule here


    @defer.inlineCallbacks
    def _getConnection(self, connection_id, requester_nsa):
        # add security check sometime
        conns = yield Simplebackendconnection.findBy(connection_id=connection_id)
        if len(conns) == 0:
            raise error.ConnectionNonExistentError('No connection with id %s' % connection_id)
        defer.returnValue( conns[0] ) # we only get one, unique in db


    def logStateUpdate(self, conn, state_msg):
        log.msg('Link: %s, %s -> %s : %s.' % (conn.connection_id, conn.source_port, conn.dest_port, state_msg), system=self.log_system)


    @defer.inlineCallbacks
    def reserve(self, requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_params):

        # return defer.fail( error.InternalNRMError('test reservation failure') )

        # should perhaps verify nsa, but not that important

        if connection_id:
            raise ValueError('Cannot handle cases with existing connection id (yet)')
            #conns = yield Simplebackendconnection.findBy(connection_id=connection_id)

        # need to check schedule

        #connection_id = str(uuid.uuid1())
        connection_id = str(random.randint(10000,99999))

        source_stp = service_params.source_stp
        dest_stp   = service_params.dest_stp

        # resolve nrm ports from the topology

        if len(source_stp.labels) == 0:
            raise error.TopologyError('Source STP must specify a label')
        if len(dest_stp.labels) == 0:
            raise error.TopologyError('Destination STP must specify a label')

        if len(source_stp.labels) > 1:
            raise error.TopologyError('Source STP specifies more than one label. Only one label is currently supported')
        if len(dest_stp.labels) > 1:
            raise error.TopologyError('Destination STP specifies more than one label. Only one label is currently supported')

        # choose a label to use :-)
        src_label_value = str( source_stp.labels[0].randomLabel() )
        dst_label_value = str( dest_stp.labels[0].randomLabel() )

#        nrm_src_port = self.topology.getNetwork(self.network).getInterface(link.src_port) + '.' + src_label_value
#        nrm_dst_port = self.topology.getNetwork(self.network).getInterface(link.dst_port) + '.' + dst_label_value

        # update the connection service params to say which label was choosen here
        src_labels = [ nsa.Label(source_stp.labels[0].type_, src_label_value) ]
        dst_labels = [ nsa.Label(dest_stp.labels[0].type_, dst_label_value) ]

        conn = Simplebackendconnection(connection_id=connection_id, revision=0, global_reservation_id=global_reservation_id, description=description, nsa=provider_nsa,
                                       reserve_time=datetime.datetime.utcnow(),
                                       reservation_state=state.INITIAL, provision_state=state.SCHEDULED, activation_state=state.INACTIVE, lifecycle_state=state.INITIAL,
                                       source_network=source_stp.network, source_port=source_stp.port, source_labels=src_labels,
                                       dest_network=dest_stp.network, dest_port=dest_stp.port, dest_labels=dst_labels,
                                       start_time=service_params.start_time, end_time=service_params.end_time,
                                       bandwidth=service_params.bandwidth)
        yield conn.save()


        state.reserving(conn)
        self.logStateUpdate(conn, 'RESERVING')
        state.reserved(conn)
        self.logStateUpdate(conn, 'RESERVED')
        # need to schedule 2PC timeout

        self.schedulers[connection_id] = scheduler.TransitionScheduler()
        self.schedulers[connection_id].scheduleTransition(conn.end_time, self.terminate, state.TERMINATING)

        sc_source_stp = nsa.STP(source_stp.network, source_stp.port, labels=src_labels)
        sc_dest_stp   = nsa.STP(dest_stp.network,   dest_stp.port,   labels=dst_labels)
        sp = nsa.ServiceParameters(service_params.start_time, service_params.end_time, sc_source_stp, sc_dest_stp, service_params.bandwidth)
        rig = (global_reservation_id, description, connection_id, sp)
        defer.returnValue(rig)


    @defer.inlineCallbacks
    def provision(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        def activationSuccess(_):
            self.scheduler.scheduleTransition(self.service_parameters.end_time, self.terminate, state.TERMINATING)
            self.state.active()
            self.logStateUpdate(conn, 'ACTIVE')

        def activationFailure(err):
            log.msg('Error setting up connection: %s' % err.getErrorMessage())
            self.state.inactive()
            self.logStateUpdate(conn, 'INACTIVE')
            return err

        def doActivate(conn):
            #self.state.activating()
            state.activating(conn)
            self.logStateUpdate(conn, 'ACTIVATING')

            d = self.connection_manager.setupLink(conn.source_port, conn.dest_port)
            d.addCallbacks(activationSuccess, activationFailure)
            return d


        conn = yield self._getConnection(connection_id, requester_nsa)

        dt_now = datetime.datetime.now(tzutc())
        if conn.end_time <= dt_now:
            raise error.ConnectionGone('Cannot provision connection after end time (end time: %s, current time: %s).' % (conn.end_time, dt_now))

        yield state.provisioning(conn)
        self.logStateUpdate(conn, 'PROVISIONED')

        self.schedulers[connection_id].cancelTransition()

        if conn.start_time <= dt_now:
            d = doActivate(conn)
        else:
            self.schedulers[connection_id].scheduleTransition(conn.start_time, lambda : doActivate(conn), state.ACTIVATING)

        yield state.provisioned(conn)
        self.logStateUpdate(conn, 'PROVISIONED')
        defer.returnValue(conn.connection_id)


    @defer.inlineCallbacks
    def release(self, requester_nsa, provider_nsa, session_security_attr, connection_id):

        conn = yield self._getConnection(connection_id, requester_nsa)

        state.releasing(conn)
        self.logStateUpdate(conn, 'RELEASING')

        self.schedulers[connection_id].cancelTransition()

        if conn.activation_state == state.ACTIVE:
            yield state.deactivating(conn)
            self.logStateUpdate(conn, state.DEACTIVATING)
            try:
                yield self.connection_manager.teardownLink(self.source_port, self.dest_port)
                yield state.inactive(conn)
            except Exception as e:
                log.msg('Error terminating connection: %s' % r.getErrorMessage())

        self.schedulers[connection_id].scheduleTransition(conn.end_time, self.terminate, state.TERMINATING)

        state.scheduled(conn)
        self.logStateUpdate(conn, 'RELEASED')
        defer.returnValue(conn.connection_id)


    @defer.inlineCallbacks
    def terminate(self, requester_nsa, provider_nsa, session_security_attr, connection_id):
        # return defer.fail( error.InternalNRMError('test termination failure') )

        conn = yield self._getConnection(connection_id, requester_nsa)

        if conn.lifecycle_state == state.TERMINATED:
            defer.returnValue(conn.cid)

        yield state.terminating(conn)
        self.logStateUpdate(conn, state.TERMINATING)

        self.schedulers[connection_id].cancelTransition()

        if conn.activation_state == state.ACTIVE:
            yield state.deactivating(conn)
            self.logStateUpdate(conn, state.DEACTIVATING)
            try:
                yield self.connection_manager.teardownLink(self.source_port, self.dest_port)
                yield state.inactive(conn)
                # we can only remove resource reservation entry if we succesfully shut down the link :-(
                self.calendar.removeConnection(self.source_port, self.service_parameters.start_time, self.service_parameters.end_time)
                self.calendar.removeConnection(self.dest_port  , self.service_parameters.start_time, self.service_parameters.end_time)
            except Exception as e:
                log.msg('Error terminating connection: %s' % r.getErrorMessage())

        yield state.terminated(conn)
        self.logStateUpdate(conn, 'TERMINATED')
        defer.returnValue(conn.connection_id)



    def query(self, query_filter):
        pass


