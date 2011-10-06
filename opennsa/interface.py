"""
OpenNSA interfaces.

These are mostly here for thinking and documentation.

It is mostly a refelection of the NSI primitives.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""



from zope.interface import Interface



class NSIInterface(Interface):


    def reservation(requester_nsa, provider_nsa, session_security_attr, global_reservation_id, description, connection_id, service_parameters):
        """
        Make a path reservation.
        """

#    def reservationConfirmed(requester_nsa, provider_nsa, global_reservation_id, description, connection_id, service_parameters):
#        """
#        Confirm a reservation.
#        """
#
#    def reservationFailed(requester_nsa, provider_nsa, global_reservation_id, connection_id, connection_state, service_exception):
#        """
#        Notify that a reservation has failed.
#        """

    def provision(requester_nsa, provider_nsa, session_security_attr, connection_id):
        """
        Provisions a path.
        """

    def release(requester_nsa, provider_nsa, session_security_attr, connection_id):
        """
        Release the path from provisioned mode.
        """

    def terminate(requester_nsa, provider_nsa, session_security_attr, connection_id):
        """
        Cancels a reservation.
        """

    def query(requester_nsa, provider_nsa, session_security_attr, query_filter):
        """
        Query reservations and provisions.
        """


#class NSIClientInterface(NSIInterface):
#    pass
#

# this should go too
class NSIServiceInterface(NSIInterface):
    pass




class NSIBackendInterface(Interface):

    # is something needed to "change" a reservation / provision

    def reserve(source_endpoint, dest_endpoint, service_parameters):
        """
        Reserve a connection at the backend.

        @return: A L{defer.Deferred}, which, if successfull will fire with a
        C{string} with an internal reservation id.
        """

    def terminate(reservation_id):
        """
        Cancal a reservation at the network backend.
        """

    def provision(reservation_id):
        """
        Provisions a connection.

        @return: A L{defer.Deferred}, which, if successfull will fire with a
        C{string} with an internal connection id.
        """

    def releaseProvision(connection_id):
        """
        Release the path from provisioned mode.

        @return: A L{defer.Deferred}, which if successfull will fire with a
        C{string} with reservation id.
        """

    def query(query_filter):
        """
        Queries the backend.
        """

