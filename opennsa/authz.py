"""
Authorization functinonality.

Part of this was originally in the toplogy module and some other in the NSI2
protocol stack, but it got weird due to cross-cutting concerns, so this was
made.

Author: Henrik Thostrup Jensen <htj@nordu.net>

Copyright: NORDUnet (2015)
"""

from opennsa import nsa


NSA        = 'nsa'
USER       = 'user'
GROUP      = 'group'
TOKEN      = 'token'

AUTH_ATTRIBUTES = [ NSA, USER, GROUP, TOKEN ]


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




def isAuthorized(port, security_attributes, stp, start_time, end_time):
    """
    Check if a request is authorized to use a certain port within the given criteria.
    """
    default = True # We might want to be able to change this sometime

    for rule in port.authz:

        if any( [ rule.match(sa) for sa in security_attributes ] ):
            return True

    return default


