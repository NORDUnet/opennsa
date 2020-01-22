"""
Logging functionality.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

import time

from zope.interface import implementer

from twisted.python import log


# almost iso, we dump the T in the middle (makes it more tricky to read imho)
TIME_FORMAT = "%Y-%m-%d %H:%M:%SZ"



@implementer(log.ILogObserver)
class DebugLogObserver(log.FileLogObserver):

    def __init__(self, file_, debug=False, profile=False, payload=False):
        log.FileLogObserver.__init__(self, file_)
        self.debug = debug
        self.profile = profile
        self.payload = payload


    def formatTime(self, when):
        # over ride default time format so we get logs in utc time
        # utc time is strongly preferable when debuggin systems across multiple timezones
        iso_time_string = time.strftime(TIME_FORMAT, time.gmtime(when))
        return iso_time_string


    def emit(self, eventDict):

        if self.debug is False and eventDict.get('debug', False):
            pass # don't print debug messages if we didn't ask for it
        elif self.profile is False and eventDict.get('profile', False):
            pass # don't print profile messages if we didn't ask for it
        elif self.payload is False and eventDict.get('payload', False):
            pass # don't print payload message if we didn't ask for it
        else:
            log.FileLogObserver.emit(self, eventDict)

