
from zope.interface import implements

from twisted.python import log



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

