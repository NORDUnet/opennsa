"""
Various errors (exceptions) for OpenNSA.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

from twisted.python import log

LOG_SYSTEM = 'error'

# NSI Error codes:
#
# PAYLOAD_ERROR               00100
#   MISSING_PARAMETER         00101
#   UNSUPPORTED_PARAMETER     00102
#   NOT_IMPLEMENTED           00103
#   VERSION_NOT_SUPPORTED     00104
#
# CONNECTION_ERROR            00200
#   INVALID_TRANSITION        00201
#   CONNECTION_EXISTS         00202
#   CONNECTION_NONEXISTENT    00203
#   CONNECTION_GONE           00204
#   CONNECTION_CREATE_ERROR   00205
#
# SECURITY_ERROR              00300
#   AUTHENTICATION_FAILURE    00301
#   UNAUTHORIZED              00302
#
# TOPOLOGY_ERROR              00400
#   UNKNOWN_STP               00401             # DEPRECATED 00701
#   STP_RESOLUTION_ERROR      00402             # DEPRECATED 00702
#   NO_PATH_FOUND             00403
#   VLANID_INTERCANGE_NOT_SUPPORTED 00404       # DEPRECATED 00703
#
# INTERNAL_ERROR              00500
#   INTERNAL_NRM_ERROR        00501
#
# RESOURCE_UNAVAILABLE        00600
#   STP_UNAVALABLE            00601             # DEPRECATED 00704
#   BANDWIDTH_UNAVAILABLE     00602             # DEPRECATED 00705

# P2P Service Specific Errors
#
# SERVICE_ERROR 00700
#   UNKNOWN_STP 00701
#   STP_RESOLUTION_ERROR 00702
#   VLANID_INTERCANGE_NOT_SUPPORTED 00703
#   STP_UNAVALABLE 00704
#   CAPACITY_UNAVAILABLE 00705


## Errors which are/should only be used internally

class CallbackTimeoutError(Exception):
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
    nsaId   = None
    connectionId = None
    variables    = None

    def __init__(self, message, nsa_id=None, connection_id=None, variables=None):
        Exception.__init__(self, message)
        self.nsaId = nsa_id
        self.connectionId = connection_id
        self.variables = variables # [ ( variable, value ) ]


class UnknownNSIError(NSIError):
    # used when we get a bad error id - it happens
    pass


class PayloadError(NSIError):

    errorId = '00100'


class MissingParameterError(PayloadError):

    errorId = '00101'


class UnsupportedParameter(PayloadError):

    errorId = '00102'


class ConnectionError(NSIError):

    errorId = '00200'


class InvalidTransitionError(ConnectionError):

    errorId = '00201'


class ConnectionExistsError(ConnectionError):

    errorId = '00202'


class ConnectionNonExistentError(ConnectionError):

    errorId = '00203'


class ConnectionGoneError(ConnectionError):

    errorId = '00204'


class ConnectionCreateError(ConnectionError):

    errorId = '00205'


class SecurityError(NSIError):

    errorId = '00300'


class UnauthorizedError(SecurityError):

    errorId = '00302'


class TopologyError(NSIError):

    errorId = '00400'


class NoPathFoundError(NSIError):

    errorId = '00403'


class InternalServerError(NSIError):

    errorId = '00500'


class InternalNRMError(InternalServerError):

    errorId = '00501'


class DownstreamNSAError(InternalServerError):

    errorId = '00505' # NOT OFFICAL ERROR CODE


class ResourceUnavailableError(NSIError):

    errorId = '00600'


class ServiceError(NSIError): # please do not use this ugly mf

    errorId = '00700'


class UnknownSTPError(ServiceError):

    errorId = '00701'


class STPResolutionError(NSIError):

    errorId = '00702'


class VLANInterchangeNotSupportedError(TopologyError):

    errorId = '00703'


class STPUnavailableError(ServiceError, TopologyError): # need this to be a topology error internally

    errorId = '00704'


class BandwidthUnavailableError(ServiceError): # NSI error name is CAPACITY_UNAVAILABLE

    errorId = '00705'



NSI_ERROR_CODE_TABLE = {
    '00100' : PayloadError,
    '00101' : MissingParameterError,
    '00200' : ConnectionError,
    '00201' : InvalidTransitionError,
    '00202' : ConnectionExistsError,
    '00203' : ConnectionNonExistentError,
    '00204' : ConnectionGoneError,
    '00205' : ConnectionCreateError,
    '00300' : SecurityError,
    '00302' : UnauthorizedError,
    '00400' : TopologyError,
    '00401' : UnknownSTPError,                      # compat
    '00402' : STPResolutionError,                   # compat
    '00403' : NoPathFoundError,
    '00404' : VLANInterchangeNotSupportedError,     # compat
    '00500' : InternalServerError,
    '00501' : InternalNRMError,
    '00600' : ResourceUnavailableError,
    '00601' : STPUnavailableError,                  # compat
    '00602' : BandwidthUnavailableError,            # compat
    '00701' : UnknownSTPError,
    '00702' : STPResolutionError,
    '00703' : VLANInterchangeNotSupportedError,
    '00704' : STPUnavailableError,
    '00705' : BandwidthUnavailableError             # compat
}


def lookup(error_code):

    if not (type(error_code) is str and len(error_code) == 5):
        log.msg('Invalid Error Code (type or length is wrong). Error code: %s' % error_code, system=LOG_SYSTEM)
        return UnknownNSIError

    ex = NSI_ERROR_CODE_TABLE.get(error_code)
    if ex is None:
        generic_error_code = error_code[0:3] + '00'
        ex = NSI_ERROR_CODE_TABLE.get(generic_error_code)

    if ex is None:
        raise ValueError('Could not find error type. Invalid error code: %s' % error_code)

    return ex

