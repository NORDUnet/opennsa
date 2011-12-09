"""
Functionality for reading default for the OpenNSA CLI defaults file.
"""

import time
import datetime

from twisted.python import log


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
            if option in ('starttime', 'endtime'):
                if value.startswith('+'):
                    offset = int(value[1:])
                    value = datetime.datetime.utcfromtimestamp(time.time() + offset)
                else:
                    value = datetime.datetime.strptime(value, XSD_DATETIME_FORMAT)

            defaults[option] = value

        except Exception, e:
            log.msg('Error parsing line "%s" in defaults file. Error: %s' % (line, str(e)))

    return defaults

