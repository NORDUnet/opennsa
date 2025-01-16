"""
Backend reservation calendar.

Keeps track of reservation timeslots for resources.

Inteded usage is for NRM backend which does not have their own reservation calendar.

The module assumes that any expired reservations are removed. Otherwise the
overlap detection will not work properly.

None is allowed for start and end time. In that case the semantics is now for
start time and forever for end time.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2016)
"""

import datetime

from opennsa import error



class ReservationCalendar:

    def __init__(self):
        self.reservations = [] # [ ( resource, start_time, end_time ) ]


    def _checkArgs(self, resource, start_time, end_time):
        assert type(resource)    is str, 'Resource must be a string'

        assert start_time is None or type(start_time) is datetime.datetime, 'Start time must be a datetime object or None, not %s' % str(type(start_time))
        assert end_time   is None or type(end_time)   is datetime.datetime, 'End time must be a datetime object or None, not %s' % str(type(end_time))

        if start_time is not None:
            assert start_time.tzinfo is None, 'Start time must NOT have time zone.'
        if end_time is not None:
            assert end_time.tzinfo   is None, 'End time must NOT have time zone.'


    def addReservation(self, resource, start_time, end_time):
        self._checkArgs(resource, start_time, end_time)

        reservation = (resource, start_time, end_time)
        self.reservations.append(reservation)


    def removeReservation(self, resource, start_time, end_time):
        self._checkArgs(resource, start_time, end_time)

        reservation = (resource, start_time, end_time)
        try:
            self.reservations.remove(reservation)
        except ValueError:
            raise ValueError('Reservation (%s, %s, %s) does not exist. Cannot remove' % (resource, start_time, end_time))


    def checkReservation(self, resource, start_time, end_time):
        self._checkArgs(resource, start_time, end_time)

        # check start time is before end time
        if start_time is not None and end_time is not None and start_time > end_time:
            raise error.PayloadError('Invalid request: Reverse duration (end time before start time)')

        if start_time is not None:
            # check that start time is not in the past
            now = datetime.datetime.utcnow()
            if start_time < now:
                delta = now - start_time
                stamp = str(start_time).rsplit('.')[0]
                variables = [ ('startTime', start_time.isoformat() ) ]
                raise error.PayloadError('Invalid request: Start time in the past (Startime: %s, Delta: %s)' % (stamp, str(delta)), variables=variables )

            # check the start time makes sense
            if start_time > datetime.datetime(2095, 1, 1):
                raise error.PayloadError('Invalid request: Start time after year 2095')

        for (c_resource, c_start_time, c_end_time) in self.reservations:
            if resource == c_resource:
                if self._resourceOverlap(c_start_time, c_end_time, start_time, end_time):
                    raise error.STPUnavailableError('Resource %s not available in specified time span' % resource)

        # all good


    def _resourceOverlap(self, res1_start_time, res1_end_time, res2_start_time, res2_end_time):
        # resource temporal availability

        # hack on
        # instead of doing a lot of complicated branching for None checking, we just coalesce the values into something easier

        now = datetime.datetime.utcnow()
        forever = datetime.datetime(9999, 1, 1)

        r1s = res1_start_time or now
        r2s = res2_start_time or now
        r1e = res1_end_time or forever
        r2e = res2_end_time or forever

        assert r1s < r1e, 'Cannot detect overlap for backwards reservation (1)'
        assert r2s < r2e, 'Cannot detect overlap for backwards reservation (2)'

        if r2e < r1s:
            return False # res2 ends before res1 starts so it is ok
        if r2s > r1e:
            return False # res2 starts after res1 ends so it is ok

        # resources overlap in time
        return True

