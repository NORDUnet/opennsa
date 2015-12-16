"""
Authorization functinonality.

Part of this was originally in the toplogy module and some other in the NSI2
protocol stack, but it got weird due to all the cross-cutting concerns, so this
was made.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2015)
"""

from twisted.python import log

from opennsa import nsa


NSA        = 'nsa'
USER       = 'user'
GROUP      = 'group'
TOKEN      = 'token'    # To allow static tokens - not sure this is something we want long term
HOST_DN    = 'hostdn'   # X509 subject host distinguised name

HEADER_ATTRIBUTES  = [ NSA, USER, GROUP, TOKEN, HOST_DN ]
REQUEST_ATTRIBUTES = [ HOST_DN ]

AUTH_ATTRIBUTES = HEADER_ATTRIBUTES + REQUEST_ATTRIBUTES



# Authorization Rules / Policies

class AuthorizationRule(object):
    pass



class AuthorizationAttribute(AuthorizationRule):

    def __init__(self, type_, value):
        self.type_ = type_
        self.value = value


    def match(self, sa):
        assert type(sa) is nsa.SecurityAttribute, 'Can only match AuthorizationRule with a SecurityAttribute'
        return self.type_ == sa.type_ and self.value == sa.value



def isAuthorized(port, security_attributes, stp, request_info, start_time, end_time):
    """
    Check if a request is authorized to use a certain port within the given criteria.
    """
    default = False if port.authz else True

    for rule in port.authz:
        if rule.type_ in HEADER_ATTRIBUTES:
            if any( [ rule.match(sa) for sa in security_attributes ] ):
                return True
        elif rule.type_ in REQUEST_ATTRIBUTES and rule.type_ == HOST_DN:
            if rule.value == request_info.cert_host_dn:
                return True
        else:
            log.msg("Couldn't figure out what to do with rule of type %s" % rule.type_, system='AuthZ')

    return default

