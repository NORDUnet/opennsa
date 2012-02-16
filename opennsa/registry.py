"""
Event handling system.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012)
"""


RESERVE               = 'reserve'
RESERVE_RESPONSE      = 'reserve_response'
PROVISION             = 'provision'
PROVISION_RESPONSE    = 'provision_response'
RELEASE               = 'release'
RELEASE_RESPONSE      = 'release_response'
TERMINATE             = 'terminate'
TERMINATE_RESPONSE    = 'terminate_response'
QUERY                 = 'query'
QUERY_RESPONSE        = 'query_response'
FORCED_END            = 'forced_end'

SYSTEM_SERVICE        = 'service'



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

