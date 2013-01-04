"""
Multi-backend backend :-)

I.e., a backend which makes several backends look as one.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012)
"""

from twisted.python import log

from zope.interface import implements

from twisted.internet import defer

from opennsa import nsa, error, state, interface as nsainterface
from opennsa.backends.common import scheduler


LOG_SYSTEM = 'opennsa.MultiBackend'


class MultiBackendNSIBackend:

    implements(nsainterface.NSIBackendInterface)

    def __init__(self, network_name, backends, internal_topology):
        self.network_name = network_name
        self.backends = backends
        self.internal_topology = internal_topology
        self.connections = []


    def createConnection(self, source_port, dest_port, service_parameters):

        def portToSTP(port):
            node, int_port = port.split(':',2)
            return nsa.STP(node, int_port)

        # convert nrm ports to stps so the topology module will understand it
        source = portToSTP(source_port)
        dest   = portToSTP(dest_port)

        # 1: enumerate possible internal connections
        paths = self.internal_topology.findPaths(source, dest, None)

        # 2: prune possible connections by asking backends which connections are possible

        def isPathReservable(path):
            for link in path.network_links:
                backend = self.backends.get(link.network, None)
                if backend is None:
                    log.msg('Internal link specified for unknown node (%s).' % link.network, system=LOG_SYSTEM)
                    return False
                try:
                    return backend.canAllocateLink(link.source, link.dest, service_parameters)
                except error.NSIError as e:
                    log.msg('Rejecting internal link candidate: %s. Reason %s' % (link, e))
                    return False

        pruned_paths = [ path for path in paths if isPathReservable(path) ]

        # 3: select connection to use
        candidate_path = pruned_paths.pop(0) # first is always the best :-)

        log.msg('Candidate path for internal connection: %s' % str(candidate_path))

        # 4: setup connections
        connections = []
        for link in candidate_path.network_links:
            backend = self.backends[link.network]
            conn = backend.createConnection(link.source, link.dest, service_parameters)
            connections.append(conn)

        conn = MultiBackendConnection(source_port, dest_port, connections, service_parameters, 'Multi NRM %s' % self.network_name)
        self.connections.append(conn)
        return conn



class MultiBackendConnection:

    def __init__(self, source_port, dest_port, sub_connections, service_parameters, log_system):
        self.source_port = source_port
        self.dest_port = dest_port
        self.sub_connections = sub_connections
        self.service_parameters = service_parameters
        self.log_system = log_system

        self.state = state.ConnectionState()
        self.scheduler = scheduler.TransitionScheduler()

        # STPs and curator is still needed

    # A lot of this functionality is similar to inter-domain connection aggregator
    # It should be possible to have some of this go into a common superclass
    # Will require methods for logging / event handling

    def curator(self):
        return 'Multi'

    def stps(self):
        return self.service_parameters.source_stp, self.service_parameters.source_stp


    def connections(self):
        return self.sub_connections


    def reserve(self):

        def scheduled(st):
            self.state.switchState(state.SCHEDULED)
            self.scheduler.scheduleTransition(self.service_parameters.end_time, self.state.switchState, state.TERMINATED)
            return self

        def reserveRequestsDone(results):
            successes = [ r[0] for r in results ]
            if all(successes):
                self.state.switchState(state.RESERVED)
                log.msg('Reservations(%i) succeeded' % len(self.connections()), system=LOG_SYSTEM)
                self.scheduler.scheduleTransition(self.service_parameters.start_time, scheduled, state.SCHEDULED)
#                self.eventDispatch(registry.RESERVE_RESPONSE, True, self)

            else:
                raise NotImplementedError('ARG!')

        self.state.switchState(state.RESERVING)

        defs = [ sc.reserve() for sc in self.connections() ]

        dl = defer.DeferredList(defs, consumeErrors=True)
        dl.addCallback(reserveRequestsDone) # never errbacks
        return dl


    def provision(self):

        print "MULTI PROVISION"
        self.scheduler.cancelTransition()
        self.state.switchState(state.PROVISIONING)
        self.state.switchState(state.PROVISIONED)
        return defer.succeed(self), defer.succeed(self)

    def release(self):

        print "MULTI RELEASE"
        self.scheduler.cancelTransition()
        self.state.switchState(state.RELEASING)
        self.state.switchState(state.SCHEDULED)
        return defer.succeed(self)

    def terminate(self):

        print "MULTI TERMINATE"
        self.scheduler.cancelTransition()
        self.state.switchState(state.TERMINATING)
        self.state.switchState(state.TERMINATED)
        return defer.succeed(self)

#    def setupLink(self, source_port, dest_port):
#        log.msg('Link %s -> %s up' % (source_port, dest_port), system=self.log_system)
#        return defer.succeed(None)
#        #return defer.fail(NotImplementedError('Link setup failed'))
#
#
#    def teardownLink(self, source_port, dest_port):
#        log.msg('Link %s -> %s down' % (source_port, dest_port), system=self.log_system)
#        return defer.succeed(None)
#        #return defer.fail(NotImplementedError('Link teardown failed'))
#
