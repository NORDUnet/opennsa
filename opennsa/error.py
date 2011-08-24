"""
Various errors (exceptions) for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""


class CallbackTimeoutError(Exception):
    pass


class TopologyError(Exception):
    pass


class NoSuchConnectionError(Exception):
    pass


class ConnectionStateTransitionError(Exception):
    pass


class ReserveError(Exception):
    pass


class CancelReservationError(Exception):
    pass


class ProvisionError(Exception):
    pass


class ReleaseProvisionError(Exception):
    pass


class QueryError(Exception):
    pass


