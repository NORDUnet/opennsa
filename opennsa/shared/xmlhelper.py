"""
Various XML utility functions (actually just ISO datetime).

Author: Henrik Thostrup Jensen <htj _at_ nordu.net>
Copyright: NORDUnet (2012-2015)
"""

import datetime

from opennsa import error

from dateutil import parser


class UTC(datetime.tzinfo):

    def utcoffset(self, dt):
        return datetime.timedelta(0)

    def dst(self, dt):
        return datetime.timedelta(0)

    def tzname(self, dt):
        return "UTC"


def createXMLTime(timestamp):
    # we assume this is without tz info and in utc time, because that is how it should be in opennsa
    assert timestamp.tzinfo is None, 'timestamp must be without time zone information'
    return timestamp.isoformat() + 'Z'


def parseXMLTimestamp(xsd_timestamp):

    dt = parser.isoparse(xsd_timestamp)

    if dt.utcoffset() is None:
        # this needs to changed to valueerror...
        raise error.PayloadError('Timestamp has no time zone information')

    # convert to utc and remove tz info (internal use)
    utc_dt = dt.astimezone(UTC()).replace(tzinfo=None)
    return utc_dt

