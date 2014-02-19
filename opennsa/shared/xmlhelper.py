"""
Various XML utility functions.

Author: Henrik Thostrup Jensen <htj _at_ nordu.net>
Copyright: NORDUnet (2012-2014)
"""

from dateutil import parser
from dateutil.tz import tzutc



def createXMLTime(timestamp):
    # we assume this is without tz info and in utc time, because that is how it should be in opennsa
    assert timestamp.tzinfo is None, 'timestamp must be without time zone information'
    return timestamp.isoformat() + 'Z'


def parseXMLTimestamp(xsd_timestamp):

    xtp = parser.parser()

    dt = xtp.parse(xsd_timestamp)
    if dt.utcoffset() is None:
        # this needs to changed to valueerror...
        from opennsa import error
        raise error.PayloadError('Timestamp has no time zone information')

    # convert to utc and remove tz info (internal use)
    utc_dt = dt.astimezone(tzutc()).replace(tzinfo=None)
    return utc_dt



