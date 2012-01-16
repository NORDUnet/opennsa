"""
Logging functionality.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2012)
"""

import sys

from zope.interface import implements

from twisted.python import log



class EarlyObserver:

    def emit(self, eventDict):
        msg = ''.join(eventDict['message'])
        sys.stdout.write('#' + msg + "\n")
        sys.stdout.flush()

    def stop(self):
        log.removeObserver(self.emit)



class DebugLogObserver(log.FileLogObserver):

    implements(log.ILogObserver)

    def __init__(self, file_, debug=False):
        log.FileLogObserver.__init__(self, file_)
        self.debug = debug


    def emit(self, eventDict):

        if self.debug is False and eventDict.get('debug', False):
            pass # don't print debug messages if we didn't ask for it
        else:
            log.FileLogObserver.emit(self, eventDict)

