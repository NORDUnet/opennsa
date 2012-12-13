"""
Various errors (exceptions) for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

# NSI Error codes:
#
# PAYLOAD_ERROR             00100
#   MISSING_PARAMETER         00101
#   UNSUPPORTED_PARAMETER     00102
# NOT_IMPLEMENTED           00103
#   VERSION_NOT_SUPPORTED     00104
#   CONNECTION_ERROR          00200
#   INVALID_TRANSITION        00201
#   CONNECTION_EXISTS         00202
#   CONNECTION_NONEXISTENT    00203
#   CONNECTION_GONE           00204
#   CONNECTION_CREATE_ERROR   00205
# SECURITY_ERROR            00300
#   AUTHENTICATION_FAILURE    00301
#   UNAUTHORIZED              00302
# TOPOLOGY_ERROR            00400
#   UNKNOWN_STP               00401
#   STP_RESOLUTION_ERROR      00402
#   NO_PATH_FOUND             00403
#   VLANID_INTERCANGE_NOT_SUPPORTED 00404
# INTERNAL_ERROR            00500
#   INTERNAL_NRM_ERROR        00501
#   RESOURCE_UNAVAILABLE      00600
# STP_UNAVALABLE            00601
#   BANDWIDTH_UNAVAILABLE     00602


## Errors which are/should only be used internally

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


## NSI Errors


class NSIError(Exception):
    """
    This class is only used to indicate that an exception class is a "proper"
    NSI error, and have an errorId that can be used to produce a message with
    an errorId in it.

    It should not be instantiated directly.
    """
    errorId = None


class PayloadError(NSIError):

    errorId = '00100'


class ConnectionError(NSIError):

    errorId = '00200'


class ConnectionExistsError(ConnectionError):

    errorId = '00202'



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


