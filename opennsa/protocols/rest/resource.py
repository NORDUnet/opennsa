"""
REST API for connections.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2015)
"""

import time
import json

from twisted.python import log, failure
from twisted.internet import defer
from twisted.web import resource, server

from opennsa import nsa, error, state, constants as cnt, database
from opennsa.shared import xmlhelper
from opennsa.protocols.shared import requestauthz
from opennsa.protocols.nsi2 import helper



LOG_SYSTEM='protocol.rest'
RN = '\r\n'

CONTENT_LENGTH = 'content-length' # twisted.web doesn't have this as a constant


def _requestResponse(request, code, payload, headers=None):
    # helper
    request.setResponseCode(code)
    request.setHeader(CONTENT_LENGTH, len(payload))
    if headers is not None:
        for key, value in headers.items():
            request.setHeader(key, value)
    return payload


def _finishRequest(request, code, payload, headers=None):
    # helper
    _requestResponse(request, code, payload, headers)
    request.write(payload)
    request.finish()


def _errorCode(ex):
    if isinstance(ex, error.NSIError):
        return 400 # Client Error
    else:
        return 500 # Server Error


def _createErrorResponse(err, request):
    log.msg('%s while creating connection: %s' % (str(err.type), str(err.value)), system=LOG_SYSTEM)

    payload = str(err.value) + RN
    error_code = _errorCode(err.value)

    _finishRequest(request, error_code, payload)



@defer.inlineCallbacks
def conn2dict(conn):

    def label(label):
        if label is None:
            return ''
        else:
            try:
                return '?%s=%s' % (label.type_, label.labelValue())
            except Exception as err:
                log.msg('Error while converting label "%s" for connection: %s. %s: %s' % (label, conn.connection_id, str(err.type), str(err.value)), system=LOG_SYSTEM)
                return ''


    d = {}

    d['connection_id']     = conn.connection_id
    d['start_time']        = xmlhelper.createXMLTime(conn.start_time) if conn.start_time is not None else None
    d['end_time']          = xmlhelper.createXMLTime(conn.end_time)   if conn.end_time   is not None else None
    d['source']            = '%s:%s%s' % (conn.source_network, conn.source_port, label(conn.source_label))
    d['destination']       = '%s:%s%s' % (conn.dest_network, conn.dest_port, label(conn.dest_label))
    d['capacity']         = conn.bandwidth
    d['created']           = xmlhelper.createXMLTime(conn.reserve_time)
    d['reservation_state'] = conn.reservation_state
    d['provision_state']   = conn.provision_state
    d['lifecycle_state']   = conn.lifecycle_state

    # this really needs to be in the database module (aggregator uses this too)
    df = database.SubConnection.findBy(service_connection_id=conn.id)
    sub_conns = yield df

    # copied from aggregator, refactor sometime
    if len(sub_conns) == 0: # apparently this can happen
        data_plane_status = (False, 0, False)
    else:
        aggr_active     = all( [ sc.data_plane_active     for sc in sub_conns ] )
        aggr_version    = max( [ sc.data_plane_version    for sc in sub_conns ] ) or 0 # can be None otherwise
        aggr_consistent = all( [ sc.data_plane_consistent for sc in sub_conns ] )
        data_plane_status = (aggr_active, aggr_version, aggr_consistent)

    d['data_plane_active'] = conn.data_plane = data_plane_status[0]

    #return d
    defer.returnValue(d)



class P2PBaseResource(resource.Resource):
    """
    Resource for creating connections. Also creates sub-resources for connections.
    """
    def __init__(self, provider, base_path, allowed_hosts=None):
        resource.Resource.__init__(self)
        self.provider = provider
        self.base_path = base_path
        self.allowed_hosts = allowed_hosts


    def getChild(self, path, request):
        return P2PConnectionResource(self.provider, path, self.allowed_hosts)


    def render_GET(self, request):
        # this should return a list of authZed connections with some usefull information
        # we cannot really do any meaningfull authz at the moment though...

        @defer.inlineCallbacks
        def gotConnections(conns):
            res = []

            for conn in conns:
                d = yield conn2dict(conn)
                res.append(d)

            payload = json.dumps(res) + RN

            request.setResponseCode(200)
            request.setHeader("Content-Type", 'application/json')
            request.write(payload)
            request.finish()

        d = database.ServiceConnection.find()
        d.addCallbacks(gotConnections, _createErrorResponse, errbackArgs=(request,))
        return server.NOT_DONE_YET


    def render_POST(self, request):

        allowed, msg, request_info = requestauthz.checkAuthz(request, self.allowed_hosts)
        if not allowed:
            payload = msg + RN
            return _requestResponse(request, 401, payload) # Not Authorized

        payload = request.content.read()

        if len(payload) == 0:
            log.msg('No data received in request', system=LOG_SYSTEM)
            payload = 'No data received in request' + RN
            return _requestResponse(request, 400, payload) # Bad Request

        if len(payload) > 32*1024:
            log.msg('Rejecting request, payload too large. Length %i' % len(payload), system=LOG_SYSTEM)
            payload = 'Requests too large' + RN
            return _requestResponse(request, 413, payload) # Payload Too Large

        try:
            data = json.loads(payload)
        except ValueError:
            log.msg('Invalid JSON data received, returning 400', system=LOG_SYSTEM)
            payload = 'Invalid JSON data' + RN
            return _requestResponse(request, 400, payload) # Bad Request


        def createResponse(connection_id):

            payload = 'Connection created' + RN
            header = { 'location': self.base_path + '/' + connection_id }
            _finishRequest(request, 201, payload, header) # Created
            return connection_id


        # extract stuffs
        try:
            source = data['source']
            if not source.startswith(cnt.URN_OGF_PREFIX):
                source = cnt.URN_OGF_PREFIX + source

            destination = data['destination']
            if not destination.startswith(cnt.URN_OGF_PREFIX):
                destination = cnt.URN_OGF_PREFIX + destination

            source_stp = helper.createSTP(str(source))
            destination_stp = helper.createSTP(str(destination))

            start_time = xmlhelper.parseXMLTimestamp(data['start']) if 'start' in data else None
            end_time   = xmlhelper.parseXMLTimestamp(data['end'])   if 'end'   in data else None
            capacity   = data['capacity'] if 'capacity' in data else 0 # Maybe None should just be best effort

            # auto commit (default true) and auto provision (defult false)
            auto_commit     = False if 'auto_commit'    in data and not data['auto_commit'] else True
            auto_provision  = True  if 'auto_provision' in data and data['auto_provision']  else False

            if auto_provision and not auto_commit:
                msg = 'Cannot have auto-provision without auto-commit'
                log.msg('Rejecting request: ' + msg, system=LOG_SYSTEM)
                return _requestResponse(request, 400, msg + RN) # Bad Request

            # fillers, we don't really do this in this api
            symmetric = False
            ero       = None
            params    = None
            version   = 0

            service_def = nsa.Point2PointService(source_stp, destination_stp, capacity, cnt.BIDIRECTIONAL, symmetric, ero, params)
            schedule = nsa.Schedule(start_time, end_time)
            criteria = nsa.Criteria(version, schedule, service_def)

            header = nsa.NSIHeader('rest-dud-requester', 'rest-dud-provider') # completely bogus header

            d = self.provider.reserve(header, None, None, None, criteria, request_info) # nones are connection_id, global resv id, description
            d.addCallbacks(createResponse, _createErrorResponse, errbackArgs=(request,))

            if auto_commit:

                @defer.inlineCallbacks
                def connectionCreated(conn_id):
                    if conn_id is None:
                        # error creating connection
                        # not exactly optimal code flow here, but chainining the callback correctly for this is tricky
                        return

                    conn = yield self.provider.getConnection(conn_id)

                    def stateUpdate():
                        log.msg('stateUpdate reservation_state: %s, provision_state: %s' % (str(conn.reservation_state), str(conn.provision_state)), debug=True, system=LOG_SYSTEM)
                        if conn.reservation_state == state.RESERVE_HELD:
                            self.provider.reserveCommit(header, conn_id, request_info)
                        if conn.reservation_state == state.RESERVE_START and conn.provision_state == state.RELEASED and auto_provision:
                            self.provider.provision(header, conn_id, request_info)
                        if conn.provision_state == state.PROVISIONED:
                            state.desubscribe(conn_id, stateUpdate)

                    state.subscribe(conn_id, stateUpdate)

                d.addCallback(connectionCreated)

            return server.NOT_DONE_YET

        except Exception as e:
            #log.err(e, system=LOG_SYSTEM)
            log.msg('Error creating connection: %s' % str(e), system=LOG_SYSTEM)

            error_code = _errorCode(e)
            return _requestResponse(request, error_code, str(e))



class P2PConnectionResource(resource.Resource):

    def __init__(self, provider, connection_id, allowed_hosts=None):
        resource.Resource.__init__(self)
        self.provider = provider
        self.connection_id = connection_id
        self.allowed_hosts = allowed_hosts


    def getChild(self, path, request):
        if path == 'status':
            return P2PStatusResource(self.provider, self.connection_id, self.allowed_hosts)
        else:
            return resource.NoResource('Resourse does not exist')


    def render_GET(self, request):

        allowed, msg, request_info = requestauthz.checkAuthz(request, self.allowed_hosts)
        if not allowed:
            payload = msg + RN
            return _requestResponse(request, 401, payload) # Not Authorized

        d = self.provider.getConnection(self.connection_id)

        @defer.inlineCallbacks
        def gotConnection(conn):
            d = yield conn2dict(conn)

            payload = json.dumps(d) + RN
            _finishRequest(request, 200, payload, {'Content-Type': 'application/json'})

        def noConnection(err):
            payload = 'No connection with id %s' % self.connection_id
            _finishRequest(request, 404, payload)

        d.addCallbacks(gotConnection, noConnection)
        return server.NOT_DONE_YET



class P2PStatusResource(resource.Resource):

    isLeaf = 1

    def __init__(self, provider, connection_id, allowed_hosts=None):
        self.provider = provider
        self.connection_id = connection_id
        self.allowed_hosts = allowed_hosts


    # this is for longpoll
    def render_GET(self, request):

        allowed, msg, request_info = requestauthz.checkAuthz(request, self.allowed_hosts)
        if not allowed:
            request.setResponseCode(401) # Not Authorized
            return msg + RN

        def gotConnection(conn):
            request.setResponseCode(200)

            def writeStatusPayload():
                d = {}
                d['timestamp']         = int(time.time())
                d['reservation_state'] = conn.reservation_state
                d['provision_state']   = conn.provision_state
                d['lifecycle_state']   = conn.lifecycle_state

                payload = json.dumps(d) + RN
                request.write(payload)

            writeStatusPayload()
            state.subscribe(conn.connection_id, lambda : writeStatusPayload() )
            return server.NOT_DONE_YET

        def noConnection(err):
            log.msg('Connection id %s specified on longpoll request does not exist' % self.connection_id)
            request.setResponseCode(404)
            request.write('No connection with id %s' % self.connection_id)
            request.finish()

        log.msg('Longpoll state request for %s' % self.connection_id, system=LOG_SYSTEM)
        d = self.provider.getConnection(self.connection_id)
        d.addCallbacks(gotConnection, noConnection)
        return server.NOT_DONE_YET


    def render_POST(self, request):

        allowed, msg, request_info = requestauthz.checkAuthz(request, self.allowed_hosts)
        if not allowed:
            payload = msg + RN
            return _requestResponse(request, 401, payload) # Not Authorized

        state_command = request.content.read()
        state_command = state_command.upper()
        if state_command not in ('COMMIT', 'ABORT', 'PROVISION', 'RELEASE', 'TERMINATE'):
            payload = 'Invalid state command specified' + RN
            return _requestResponse(request, 400, payload) # Client Error

        header = nsa.NSIHeader('rest-dud-requester', 'rest-dud-provider') # completely bogus header

        if state_command == 'COMMIT':
            d = self.provider.reserveCommit(header, self.connection_id, request_info)
        elif state_command == 'ABORT':
            d = self.provider.reserveAbort(header, self.connection_id, request_info)
        elif state_command == 'PROVISION':
            d = self.provider.provision(header, self.connection_id, request_info)
        elif state_command == 'RELEASE':
            d = self.provider.release(header, self.connection_id, request_info)
        elif state_command == 'TERMINATE':
            d = self.provider.terminate(header, self.connection_id, request_info)
        else:
            payload = 'Unrecognized command (should not happend)' + RN
            return _requestResponse(request, 500, payload) # Server Error

        def commandDone(_):
            payload = 'ACK' + RN
            _finishRequest(request, 200, payload) # OK

        def commandError(err):
            log.msg('Error during state switch: %s' % str(err), system=LOG_SYSTEM)
            payload = str(err.getErrorMessage()) + RN
            if isinstance(err.value, error.NSIError):
                _finishRequest(request, 400, payload) # Client Error
            else:
                log.err(err)
                _finishRequest(request, 500, payload) # Server Error

        d.addCallbacks(commandDone, commandError)
        return server.NOT_DONE_YET

