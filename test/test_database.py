import datetime
import psycopg2

from twisted.internet import defer
from twisted.trial import unittest

from opennsa import state
from opennsa.backends.common import genericbackend

from . import db



class DatabaseTest(unittest.TestCase):

    def setUp(self):
        db.setupDatabase()


    @defer.inlineCallbacks
    def testReverseStartEndTimeConstraint(self):

        now = datetime.datetime.utcnow()
        start_time = now - datetime.timedelta(seconds=10)
        end_time   = now - datetime.timedelta(seconds=1000)

        conn = genericbackend.GenericBackendConnections(
            connection_id='conn-123',
            revision=0,
            global_reservation_id='gid-123',
            description='test',
            requester_nsa='req-nsa',
            reserve_time=now,
            reservation_state=state.RESERVE_START,
            provision_state=state.RELEASED,
            lifecycle_state=state.CREATED,
            data_plane_active=False,
            source_network='src-net', source_port='src-port', source_label=None,
            dest_network='dst-net', dest_port='dst-port', dest_label=None,
            start_time=start_time, end_time=end_time,
            symmetrical=False, directionality='Bidirectional', bandwidth=200,
            allocated=False
        )

        try:
            yield conn.save()
            self.fail('Should have gotten integrity error from database')
        except psycopg2.IntegrityError as e:
            pass # intended

