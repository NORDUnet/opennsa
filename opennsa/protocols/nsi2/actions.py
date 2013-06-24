"""
SOAP Actions for NSI ConnectionService version 2.
"""

# Provider

RESERVE                         = '"http://schemas.ogf.org/nsi/2013/04/connection/service/reserve"'
RESERVE_COMMIT                  = '"http://schemas.ogf.org/nsi/2013/04/connection/service/reserveCommit"'
RESERVE_ABORT                   = '"http://schemas.ogf.org/nsi/2013/04/connection/service/reserveAbort"'

PROVISION                       = '"http://schemas.ogf.org/nsi/2013/04/connection/service/provision"'
RELEASE                         = '"http://schemas.ogf.org/nsi/2013/04/connection/service/release"'
TERMINATE                       = '"http://schemas.ogf.org/nsi/2013/04/connection/service/terminate"'

QUERY_SUMMARY                   = '"http://schemas.ogf.org/nsi/2013/04/connection/service/querySummary"'
QUERY_SUMMARY_SYNC              = '"http://schemas.ogf.org/nsi/2013/04/connection/service/querySummarySync"'
QUERY_RECURSIVE                 = '"http://schemas.ogf.org/nsi/2013/04/connection/service/queryRecursive"'
QUERY_NOTIFICATION              = '"http://schemas.ogf.org/nsi/2013/04/connection/service/queryNotification"'
QUERY_NOTIFICATION_SYNC         = '"http://schemas.ogf.org/nsi/2013/04/connection/service/queryNotificationSync"'

# Reqeuster


RESERVE_CONFIRMED               = '"http://schemas.ogf.org/nsi/2013/04/connection/service/reserveConfirmed"'
RESERVE_FAILED                  = '"http://schemas.ogf.org/nsi/2013/04/connection/service/reserveFailed"'
RESERVE_COMMIT_CONFIRMED        = '"http://schemas.ogf.org/nsi/2013/04/connection/service/reserveCommitConfirmed"'
RESERVE_COMMIT_FAILED           = '"http://schemas.ogf.org/nsi/2013/04/connection/service/reserveCommitFailed"'
RESERVE_ABORT_CONFIRMED         = '"http://schemas.ogf.org/nsi/2013/04/connection/service/reserveAbortConfirmed"'

PROVISION_CONFIRMED             = '"http://schemas.ogf.org/nsi/2013/04/connection/service/provisionConfirmed"'
RELEASE_CONFIRMED               = '"http://schemas.ogf.org/nsi/2013/04/connection/service/releaseConfirmed"'
TERMINATE_CONFIRMED             = '"http://schemas.ogf.org/nsi/2013/04/connection/service/terminateConfirmed"'

QUERY_SUMMARY_CONFIRMED         = '"http://schemas.ogf.org/nsi/2013/04/connection/service/querySummaryConfirmed"'
QUERY_SUMMARY_FAILED            = '"http://schemas.ogf.org/nsi/2013/04/connection/service/querySummaryFailed"'

QUERY_RECURSIVE_CONFIRMED       = '"http://schemas.ogf.org/nsi/2013/04/connection/service/queryRecursiveConfirmed"'
QUERY_RECURSIVE_FAILED          = '"http://schemas.ogf.org/nsi/2013/04/connection/service/queryRecursiveFailed"'
QUERY_NOTIFICATION_CONFIRMED    = '"http://schemas.ogf.org/nsi/2013/04/connection/service/queryNotificationConfirmed"'

QUERY_NOTIFICATION_FAILED       = '"http://schemas.ogf.org/nsi/2013/04/connection/service/queryNotificationFailed"'
ERROR_EVENT                     = '"http://schemas.ogf.org/nsi/2013/04/connection/service/errorEvent"'
DATA_PLANE_STATE_CHANGE         = '"http://schemas.ogf.org/nsi/2013/04/connection/service/dataPlaneStateChange"'
RESERVE_TIMEOUT                 = '"http://schemas.ogf.org/nsi/2013/04/connection/service/reserveTimeout"'
MESSAGE_DELIVERY_TIMEOUT        = '"http://schemas.ogf.org/nsi/2013/04/connection/service/messageDeliveryTimeout"'

