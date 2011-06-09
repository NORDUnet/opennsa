"""
OpenNSA interfaces.

These are mostly here for thinking and documentation.

It is mostly a refelection of the NSI primitives.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""


class NSIService:


    def reserve(requester_nsa, provider_nsa, reservation_id, description, connection_id,
                service_paramters, session_security_attributes):
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

