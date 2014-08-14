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



class IPlugin(Interface):
    """
    Interface for plugins.

    An OpenNSA plugin gets called when certain actions are completed, i.e,
    reserveCommit is done or a connection is terminated. I.e., hooks.

    The actions are invoked for aggregated connections only. Local connection
    information can be found by iterating through the sub connections of the
    connection.

    It is possible to get additional hooks added it is deemed a good idea.
    Currently it is somewhat modelled after what was needed for NORDUnet.
    Hooks for data plane activation and deactivation would be obvious, but
    I haven't needed it.

    See opennsa.plugin.BasePlugin for default implementation.
    """

    def init(cfg, ctx_factory):
        """
        Called during startup.
        Config dictionary and context factory (maybe None) is provided as arguments.
        """


    def connectionRequest(header, connection_id, global_reservation_id, description, criteria):
        """
        Called when a new connection request is made.

        It is meant as way to reject request from certain policies,
        by returning a deferred that fails.

        It is not recommended to change any of the parameters, but it might work.

        @rtype: C{defer.Deferred}
        @return: A deferred which should return None. If the defer fails, the connection will
                 not be created.
        """


    def createConnectionId():
        """
        Creates a connection id for a new request. This enables assignment of service identifiers
        as some organizations have requirements for that.

        @rtype: C{defer.Deferred}
        @return: A deferred which should result in a string.
        """


    def prunePath(paths):
        """
        Called after initial path computation with the path set. The plugin can remove, add,
        or change the paths or labels.

        @rtype: C{defer.Deferred}
        @return: A deferred, which should result a list of paths.
        """


    def connectionCreated(connection):
        """
        Called when an connection has been created (committed).

        @rtype: C{defer.Deferred}
        @return: A deferred. Should return None if successfull, otherwise fail.
                 Nothing will happen on failure.
        """


    def connectionTerminated(connection):
        """
        Called when an connection has been terminated.

        @rtype: C{defer.Deferred}
        @return: A deferred. Should return None if successfull, otherwise fail.
                 Nothing will happen on failure.
        """

