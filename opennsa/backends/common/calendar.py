"""
Backend reservation calendar.

Inteded usage is for NRM backend which does not have their own reservation calendar.

Right now it is very minimal, but should be enough for basic service.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import datetime

from dateutil.tz import tzutc

from opennsa import error



class ReservationCalendar:

    def __init__(self):
        self.connections = [] # [ ( port, start_time, end_time ) ]


    def addConnection(self, port, start_time, end_time):
        # does no checking, assuming checkReservation has been called
        reservation = (port, start_time, end_time)
        self.connections.append(reservation)


    def removeConnection(self, port, start_time, end_time):
        reservation = (port, start_time, end_time)
        self.connections.remove(reservation)


    def checkReservation(self, port, start_time, end_time):
        # check types
        if not type(start_time) is datetime.datetime and type(end_time) is datetime.datetime:
            raise ValueError('Reservation start and end types must be datetime types')

        # sanity checks
        if start_time > end_time:
            raise error.PayloadError('Invalid request: Reverse duration (end time before start time)')

        now = datetime.datetime.now(tzutc())
        if start_time < now:
            delta = now - start_time
            stamp = str(start_time).rsplit('.')[0]
            raise error.PayloadError('Invalid request: Start time in the past (Startime: %s Delta: %s)' % (stamp, str(delta)))

        if start_time > datetime.datetime(2025, 1, 1, tzinfo=tzutc()):
            raise error.PayloadError('Invalid request: Start time after year 2025')

        for (c_port, c_start_time, c_end_time) in self.connections:
            if port == c_port:
                if self._portOverlap(c_start_time, c_end_time, start_time, end_time):
                    raise error.STPUnavailableError('Port %s not available in specified time span' % port)

        # all good

    # port temporal availability
    def _portOverlap(self, res1_start_time, res1_end_time, res2_start_time, res2_end_time):

        assert res1_start_time < res1_end_time, 'Refusing to detect overlap for backwards reservation (1)'
        assert res2_start_time < res2_end_time, 'Refusing to detect overlap for backwards reservation (2)'

        if res2_end_time < res1_start_time:
            return False # res2 ends before res1 starts so it is ok
        if res2_start_time > res1_end_time:
            return False # res2 starts after res1 ends so it is ok

        # ports overlap in time
        return True

