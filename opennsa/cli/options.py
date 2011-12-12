"""
Various functionality for OpenNSA CLI options.
"""

import time
import datetime

from twisted.python import log


# option names, as constants so we don't use strings in other modules
VERBOSE         = 'verbose'
DEFAULTS_FILE   = 'defaultsfile'
WSDL_DIRECTORY  = 'wsdldirectory'
HOST            = 'host'
PORT            = 'port'

TOPOLOGY_FILE   = 'topologyfile'
NETWORK         = 'network'
SERVICE_URL     = 'serviceurl'
REQUESTER       = 'requester'
PROVIDER        = 'provider'

SOURCE_STP      = 'source'
DEST_STP        = 'dest'
BANDWIDTH       = 'bandwidth'
START_TIME      = 'starttime'
END_TIME        = 'endtime'

CONNECTION_ID   = 'connection-id'
GLOBAL_ID       = 'global-id'

# other constants
XSD_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"



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
                if value.startswith('+'):
                    offset = int(value[1:])
                    value = datetime.datetime.utcfromtimestamp(time.time() + offset)
                else:
                    value = datetime.datetime.strptime(value, XSD_DATETIME_FORMAT)

            if option in (PORT, BANDWIDTH):
                value = int(value)

            defaults[option] = value

        except Exception, e:
            log.msg('Error parsing line "%s" in defaults file. Error: %s' % (line, str(e)))

    return defaults

