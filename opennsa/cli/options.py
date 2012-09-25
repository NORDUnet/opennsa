"""
Various functionality for OpenNSA CLI options.
"""

import time
import datetime

from twisted.python import log

from opennsa import config


# option names, as constants so we don't use strings in other modules
VERBOSE         = 'verbose'
DEFAULTS_FILE   = 'defaults-file'
WSDL_DIRECTORY  = 'wsdl'
HOST            = 'host'
PORT            = 'port'

TOPOLOGY_FILE   = 'topology'
NETWORK         = 'network'
SERVICE_URL     = 'service'
REQUESTER       = 'requester'
PROVIDER        = 'provider'

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
VERIFY_CERT     = config.VERIFY_CERT

FULL_GRAPH      = 'fullgraph'

# other constants
XSD_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"



def parseTimestamp(value):

    if value.startswith('+'):
        offset = int(value[1:])
        ts = datetime.datetime.utcfromtimestamp(time.time() + offset)
    else:
        ts = datetime.datetime.strptime(value, XSD_DATETIME_FORMAT)
    return ts



def readDefaults(file_):

    defaults = {}

    for line in file_.readlines():

        try:
            line = line.strip()

            if not line or line.startswith('#'):
                continue # skip comment

            option, value = line.split('=',2)

            # parse datetimes
            if option in (START_TIME, END_TIME):
                value = parseTimestamp(value)

            if option in (PORT, BANDWIDTH):
                value = int(value)

            if option in (TLS,VERIFY_CERT): # flags
                value = False if value.lower() in ('false', 'no', '0') else True

            defaults[option] = value

        except Exception, e:
            log.msg('Error parsing line "%s" in defaults file. Error: %s' % (line, str(e)))

    return defaults

