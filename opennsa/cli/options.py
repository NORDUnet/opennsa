"""
Various functionality for OpenNSA CLI options.
"""

import time
import datetime

from twisted.python import log


# option names, as constants so we don't use strings in other modules
VERBOSE         = 'verbose'
DEFAULTS_FILE   = 'defaults-file'
WSDL_DIRECTORY  = 'wsdl-directory'
HOST            = 'host'
PORT            = 'port'

TOPOLOGY_FILE   = 'topology-file'
NETWORK         = 'network'
SERVICE_URL     = 'service-url'
REQUESTER       = 'requester'
PROVIDER        = 'provider'

CONNECTION_ID   = 'connection-id'
GLOBAL_ID       = 'global-id'

SOURCE_STP      = 'source'
DEST_STP        = 'dest'
BANDWIDTH       = 'bandwidth'
START_TIME      = 'starttime'
END_TIME        = 'endtime'

PUBLIC_KEY      = 'public-key'
PRIVATE_KEY     = 'private-key'
CERTIFICATE_DIR = 'certificate-directory'

SKIP_CERT_VERIFY = 'verify-certificate'

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

            if option in (SKIP_CERT_VERIFY): # flags
                value = True if value.lower in ('true', 'yes', '1') else False

            defaults[option] = value

        except Exception, e:
            log.msg('Error parsing line "%s" in defaults file. Error: %s' % (line, str(e)))

    return defaults

