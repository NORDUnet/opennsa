"""
Event handling system.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012)
"""


DISCOVER                = 'discover'

RESERVE                 = 'reserve'
RESERVE_RESPONSE        = 'reserve_response'
RESERVE_COMMIT          = 'reserve_commit'
RESERVE_COMMIT_RESPONSE = 'reserve_commit_response'
RESERVE_ABORT           = 'reserve_abort'
RESERVE_ABORT_RESPONSE  = 'reserve_abort_response'

PROVISION               = 'provision'
PROVISION_RESPONSE      = 'provision_response'
RELEASE                 = 'release'
RELEASE_RESPONSE        = 'release_response'

TERMINATE               = 'terminate'
TERMINATE_RESPONSE      = 'terminate_response'

QUERY                   = 'query'
QUERY_RESPONSE          = 'query_response'
DATA_PLANE_CHANGE       = 'data_plane_change'


SYSTEM_SERVICE          = 'service'
NSI1_CLIENT             = 'nsi1-client'
NSI2_REMOTE             = 'nsi2-remote'
NSI2_LOCAL              = 'nsi2-local'



class ServiceRegistry:

    def __init__(self):
        self.handlers = {}


    def getHandler(self, event, system):

        es = (event, system)
        return self.handlers[es]


    def registerEventHandler(self, event, handler, system):

        if event in self.handlers:
            raise ValueError('Handler for event %s already registered' % event)

        es = (event, system)
        self.handlers[es] = handler


    def deregisterEventHandler(self, event, system):

        es = (event, system)
        self.handlers.pop(es)

