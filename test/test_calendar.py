import datetime

from twisted.trial import unittest

from opennsa import error
from opennsa.backends.common import calendar



class CalendarTest(unittest.TestCase):

    def setUp(self):
        self.c = calendar.ReservationCalendar()


    def testCheckAdd(self):

        ds = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
        de = datetime.datetime.utcnow() + datetime.timedelta(seconds=3)
        self.c.checkReservation('r1', ds, de)
        self.c.addReservation('r1', ds, de)


    def testDoubleCheckAdd(self):

        ds1 = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
        de1 = datetime.datetime.utcnow() + datetime.timedelta(seconds=3)
        ds2 = datetime.datetime.utcnow() + datetime.timedelta(seconds=5)
        de2 = datetime.datetime.utcnow() + datetime.timedelta(seconds=7)

        self.c.checkReservation('r1', ds1, de1)
        self.c.addReservation('r1', ds1, de1)

        self.c.checkReservation('r1', ds2, de2)
        self.c.addReservation('r1', ds2, de2)


    def testSimpleConflict(self):

        ds1 = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
        de1 = datetime.datetime.utcnow() + datetime.timedelta(seconds=5)
        ds2 = datetime.datetime.utcnow() + datetime.timedelta(seconds=4)
        de2 = datetime.datetime.utcnow() + datetime.timedelta(seconds=7)

        self.c.checkReservation('r1', ds1, de1)
        self.c.addReservation('r1', ds1, de2)

        self.failUnlessRaises(error.STPUnavailableError, self.c.checkReservation, 'r1', ds2, de2)


    def testStartNone(self):

        ds1 = None
        de1 = datetime.datetime.utcnow() + datetime.timedelta(seconds=5)
        ds2 = None
        de2 = datetime.datetime.utcnow() + datetime.timedelta(seconds=7)

        self.c.checkReservation('r1', ds1, de1)
        self.c.addReservation('r1', ds1, de2)

        self.failUnlessRaises(error.STPUnavailableError, self.c.checkReservation, 'r1', ds2, de2)


    def testEndNone(self):

        ds1 = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
        de1 = None
        ds2 = datetime.datetime.utcnow() + datetime.timedelta(seconds=4)
        de2 = None

        self.c.checkReservation('r1', ds1, de1)
        self.c.addReservation('r1', ds1, de2)

        self.failUnlessRaises(error.STPUnavailableError, self.c.checkReservation, 'r1', ds2, de2)


    def testStartEndNone(self):

        ds1 = None
        de1 = None
        ds2 = None
        de2 = None

        self.c.checkReservation('r1', ds1, de1)
        self.c.addReservation('r1', ds1, de2)

        self.failUnlessRaises(error.STPUnavailableError, self.c.checkReservation, 'r1', ds2, de2)


