"""
Various errors (exceptions) for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""


class CallbackTimeoutError(Exception):
    pass


class InvalidRequestError(Exception):
    pass


class ResourceNotAvailableError(Exception):
    pass


class TopologyError(Exception):
    pass


class NoSuchConnectionError(Exception):
    pass


class StateTransitionError(Exception):
    pass


# These should really be replaced with proper errors

class ReserveError(Exception):
    pass


class ProvisionError(Exception):
    pass


class ReleaseError(Exception):
    pass


class TerminateError(Exception):
    pass


class QueryError(Exception):
    pass


