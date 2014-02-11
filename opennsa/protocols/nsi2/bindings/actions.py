"""
SOAP Actions for NSI ConnectionService version 2, WSDL revision 117
"""

# Provider

RESERVE                         = '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserve"'
RESERVE_COMMIT                  = '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveCommit"'
RESERVE_ABORT                   = '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveAbort"'

PROVISION                       = '"http://schemas.ogf.org/nsi/2013/12/connection/service/provision"'
RELEASE                         = '"http://schemas.ogf.org/nsi/2013/12/connection/service/release"'
TERMINATE                       = '"http://schemas.ogf.org/nsi/2013/12/connection/service/terminate"'

QUERY_SUMMARY                   = '"http://schemas.ogf.org/nsi/2013/12/connection/service/querySummary"'
QUERY_SUMMARY_SYNC              = '"http://schemas.ogf.org/nsi/2013/12/connection/service/querySummarySync"'
QUERY_RECURSIVE                 = '"http://schemas.ogf.org/nsi/2013/12/connection/service/queryRecursive"'
QUERY_NOTIFICATION              = '"http://schemas.ogf.org/nsi/2013/12/connection/service/queryNotification"'
QUERY_NOTIFICATION_SYNC         = '"http://schemas.ogf.org/nsi/2013/12/connection/service/queryNotificationSync"'

QUERY_RESULT                    = '"http://schemas.ogf.org/nsi/2013/12/connection/service/queryResult"'
QUERY_RESULT_SYNC               = '"http://schemas.ogf.org/nsi/2013/12/connection/service/queryResultSync"'

# Requester

RESERVE_CONFIRMED               = '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveConfirmed"'
RESERVE_FAILED                  = '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveFailed"'
RESERVE_COMMIT_CONFIRMED        = '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveCommitConfirmed"'
RESERVE_COMMIT_FAILED           = '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveCommitFailed"'
RESERVE_ABORT_CONFIRMED         = '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveAbortConfirmed"'

PROVISION_CONFIRMED             = '"http://schemas.ogf.org/nsi/2013/12/connection/service/provisionConfirmed"'
RELEASE_CONFIRMED               = '"http://schemas.ogf.org/nsi/2013/12/connection/service/releaseConfirmed"'
TERMINATE_CONFIRMED             = '"http://schemas.ogf.org/nsi/2013/12/connection/service/terminateConfirmed"'

QUERY_SUMMARY_CONFIRMED         = '"http://schemas.ogf.org/nsi/2013/12/connection/service/querySummaryConfirmed"'
QUERY_RECURSIVE_CONFIRMED       = '"http://schemas.ogf.org/nsi/2013/12/connection/service/queryRecursiveConfirmed"'
QUERY_NOTIFICATION_CONFIRMED    = '"http://schemas.ogf.org/nsi/2013/12/connection/service/queryNotificationConfirmed"'
QUERY_RESULT_CONFIRMED          = '"soapAction="http://schemas.ogf.org/nsi/2013/12/connection/service/queryResultConfirmed"'

ERROR                           = '"http://schemas.ogf.org/nsi/2013/12/connection/service/error"'
ERROR_EVENT                     = '"http://schemas.ogf.org/nsi/2013/12/connection/service/errorEvent"'
DATA_PLANE_STATE_CHANGE         = '"http://schemas.ogf.org/nsi/2013/12/connection/service/dataPlaneStateChange"'
RESERVE_TIMEOUT                 = '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveTimeout"'
MESSAGE_DELIVERY_TIMEOUT        = '"http://schemas.ogf.org/nsi/2013/12/connection/service/messageDeliveryTimeout"'

