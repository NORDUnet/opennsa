"""
OpenNSA interfaces.

These are mostly here for thinking and documentation.

It is mostly a refelection of the NSI primitives.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""



from zope.interface import Interface



class INSIProvider(Interface):

    def reserve(header, connection_id, global_reservation_id, description, service_params):
        pass

    def reserveCommit(header, connection_id):
        pass

    def reserveAbort(header, connection_id):
        pass

    def provision(header, connection_id):
        pass

    def release(header, connection_id):
        pass

    def terminate(header, connection_id):
        pass

    def querySummary(header, connection_ids, global_reservation_ids):
        pass

    def queryRecursive(header, connection_ids, global_reservation_ids):
        pass

    def queryNotification(header, connection_id, start_notification, end_notification):
        pass



class INSIRequester(Interface):

    def reserveConfirmed(header, connection_id, global_reservation_id, description, criteria):
        pass

    def reserveFailed(header, connection_id, connection_states, service_exception):
        pass

    def reserveCommitConfirmed(header, connection_id):
        pass

    def reserveCommitFailed(header, connection_id, connection_states, service_exception):
        pass

    def reserveAbortConfirmed(header, connection_id):
        pass

    def provisionConfirmed(header, connection_id):
        pass

    def releaseConfirmed(header, connection_id):
        pass

    def terminateConfirmed(header, connection_id):
        pass

    def querySummaryConfirmed(header, summary_result):
        pass

    def querySummaryFailed(header, service_exception):
        pass

    def queryRecursiveConfirmed(header, recursive_result):
        pass

    def queryRecursiveFailed(header, service_exception):
        pass

    def queryNotificationConfirmed(header, notification):
        pass

    def queryNotificationFailed(header, service_exception):
        pass

    def errorEvent(header, error_event):
        pass

    def reserveTimeout(header, reserve_timeout):
        pass

    def dataPlaneStateChange(header, data_plane_status):
        pass

    def messageDeliveryTimeout(header, message_timeout):
        pass

