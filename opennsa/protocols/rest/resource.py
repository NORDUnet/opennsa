"""
REST API for connections.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2015)
"""

import json

from twisted.python import log
from twisted.web import resource, server

from opennsa import nsa, error, constants as cnt
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


    #def render_GET(self, request)
        # this should return a list of authZed connections with some usefull information


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

        # extract stuffs

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

        # fillers, we don't really do this in this api
        symmetric = False
        ero       = None
        params    = None
        version   = 0

        service_def = nsa.Point2PointService(source_stp, destination_stp, capacity, cnt.BIDIRECTIONAL, symmetric, ero, params)
        schedule = nsa.Schedule(start_time, end_time)
        criteria = nsa.Criteria(version, schedule, service_def)

        header = nsa.NSIHeader('rest-dud-requester', 'rest-dud-provider') # completely bogus header
        d = self.provider.reserve(header, None, None, None, criteria, request_info) # nones are connectoin id, global resv id, description


        def createResponse(connection_id):

            payload = 'Connection created' + RN
            header = { 'location': self.base_path + '/' + connection_id }
            _finishRequest(request, 201, payload, header) # Created

        def createErrorResponse(err):
            log.msg('%s while creating connection: %s' % (str(err.type), str(err.value)), system=LOG_SYSTEM)

            payload = str(err.value) + RN

            if isinstance(err.value, error.NSIError):
                _finishRequest(request, 400, payload) # Bad Request
            else:
                _finishRequest(request, 500, payload) # Server Error

        d.addCallbacks(createResponse, createErrorResponse)

        return server.NOT_DONE_YET



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

        def gotConnection(conn):
            #print 'connection', conn
            d = {}
            d['connection_id']     = conn.connection_id
            d['start_time']        = conn.start_time
            d['end_time']          = conn.end_time
            d['source']            = '%s:%s?%s=%s' % (conn.source_network, conn.source_port, conn.source_label.type_, conn.dest_label.labelValue())
            d['destination']       = '%s:%s?%s=%s' % (conn.dest_network, conn.dest_port, conn.dest_label.type_, conn.dest_label.labelValue())
            d['bandwidth']         = conn.bandwidth
            d['reservation_state'] = conn.reservation_state
            d['provision_state']   = conn.provision_state
            d['lifecycle_state']   = conn.lifecycle_state

            payload = json.dumps(d) + RN
            _finishRequest(request, 200, payload)

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


#    # this is for longpull, we don't have the notification infrastructure
#    def render_GET(self, request):
#
#        allowed, msg, request_info = requestauthz.checkAuthz(request, self.allowed_hosts)
#        if not allowed:
#            request.setResponseCode(401) # Not Authorized
#            return msg + RN
#
#        # not sure this one is actually needed, does pretty much the same as conn resource get
#        # actually we need this for long poll.. not sure how to pull that off though
#        d = self.provider.getConnection(self.connection_id)
#
#        def gotConnection(conn):
#            #print 'connection', conn
#            request.setResponseCode(200)
#
#            # hackish long-poll
#
#            def createStatusPayload(conn):
#                d = {}
#                d['timestamp']         = int(time.time())
#                d['reservation_state'] = conn.reservation_state
#                d['provision_state']   = conn.provision_state
#                d['lifecycle_state']   = conn.lifecycle_state
#                return json.dumps(d) + RN
#
#            payload = createStatusPayload(conn)
#            #request.write(json.dumps(d) + RN)
#            request.write(payload)
#            reactor.callLater(2, gotConnection, conn)
##            request.finish()
#            return server.NOT_DONE_YET
#
#        def noConnection(err):
#            print 'could not get connection', err
#            request.setResponseCode(404)
#            request.write('No connection with id %s' % self.connection_id)
#            request.finish()
#
#        print 'Longpull request', self.connection_id
#        d.addCallbacks(gotConnection, noConnection)
#        return server.NOT_DONE_YET



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

