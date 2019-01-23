"""
Various functionality for OpenNSA CLI options.
"""

import time
import datetime

from twisted.python import log

from opennsa import config
from opennsa.shared.xmlhelper import UTC


# option names, as constants so we don't use strings in other modules
VERBOSE         = 'verbose'
DEFAULTS_FILE   = 'defaults-file'
DUMP_PAYLOAD    = 'dump-payload'
HOST            = 'host'
PORT            = 'port'

TOPOLOGY_FILE   = 'topology'
NETWORK         = 'network'
SERVICE_URL     = 'service'
AUTHZ_HEADER    = 'authzheader'
REQUESTER       = 'requester'
PROVIDER        = 'provider'
SECURITY_ATTRIBUTES = 'securityattributes'

CONNECTION_ID   = 'connection-id'
GLOBAL_ID       = 'global-id'

SOURCE_STP      = 'source'
DEST_STP        = 'dest'
BANDWIDTH       = 'bandwidth'
START_TIME      = 'starttime'
END_TIME        = 'endtime'

TLS             = config.TLS
KEY             = config.KEY
CERTIFICATE     = config.CERTIFICATE
CERTIFICATE_DIR = config.CERTIFICATE_DIR
NO_VERIFY_CERT  = 'no-verify'

NOTIFICATION_WAIT = 'notification_wait'

# other constants
XSD_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
NSA_SHORTHAND       = 'nsa'



def parseTimestamp(value):

    if value.startswith('+'):
        offset = int(value[1:])
        ts = datetime.datetime.fromtimestamp(time.time() + offset, UTC()).replace(tzinfo=None)
    else:
        ts = datetime.datetime.strptime(value, XSD_DATETIME_FORMAT).replace(tzinfo=None)
    assert ts.tzinfo is None, 'Timestamp must NOT have time zone'
    return ts



def readDefaults(file_):

    defaults = {}

    for line in file_.readlines():

        try:
            line = line.strip()

            if not line or line.startswith('#'):
                continue # skip comment

            option, value = line.split('=',2)

            # nsa shorthand, this one is a bit special so we do it first, and continue on match
            if option == NSA_SHORTHAND:
                shorthand, nsa_id, service_url = value.split(',',3)
                defaults.setdefault(option, {})[shorthand] = (nsa_id, service_url)
                continue

            # parse datetimes
            if option in (START_TIME, END_TIME):
                value = parseTimestamp(value)

            if option in (PORT, BANDWIDTH):
                value = int(value)

            if option in (TLS,NO_VERIFY_CERT): # flags
                value = False if value.lower() in ('false', 'no', '0') else True

            defaults[option] = value


        except Exception as e:
            log.msg('Error parsing line in CLI defaults file. Line: %s. Error: %s' % (line, str(e)))

    return defaults

