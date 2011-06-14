"""
OpenNSA interfaces.

These are mostly here for thinking and documentation.

It is mostly a refelection of the NSI primitives.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""



from zope.interface import Interface



class NSIInterface(Interface):


    def reserve(requester_nsa, provider_nsa, reservation_id, description, connection_id,
                service_parameters, session_security_attributes):
        """
        Make a link reservation.
        """

    def cancelReservation(requester_nsa, provider_nsa, connection_id, session_security_attributes):
        """
        Cancel a link reservation.
        """

    def provision(requester_nsa, provider_nsa, connection_id, session_security_attributes):
        """
        Provisions a link.
        """


    def releaseProvision(requester_nsa, provider_nsa, connetion_id, session_security_attributes):
        """
        Release the link from provisioned mode.
        """


    def query(requester_nsa, provider_nsa, session_security_attributes):
        """
        Query reservations and provisions.
        """


class NSIClientInterface(NSIInterface):
    pass


class NSIService(NSIInterface):
    pass



class NSIBackendInterface(Interface):

    # is something needed to "change" a reservation / provision

    def reserve(source_endpoint, dest_endpoint, service_parameters):
        """
        Reserve a connection at the backend.

        @return: A L{defer.Deferred}, which, if successfull will fire with a
        C{string} with an internal reservation id.
        """

    def cancelReservation(reservation_id):
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
        Release the link from provisioned mode.

        @return: A L{defer.Deferred}, which if successfull will fire with a
        C{string} with reservation id.
        """

    def query(filter_attributes):
        """
        Queries the backend.
        """

