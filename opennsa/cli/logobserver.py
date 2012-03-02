"""
Simple log observer for the OpenNSA CLI util.
"""

from twisted.python import log



class SimpleObserver(log.FileLogObserver):

    debug = False

    def emit(self, eventDict):

        if 'debug' in eventDict:
            if eventDict['debug'] and self.debug:
                pass # want debug
            else:
                return # do not want debug

        text = log.textFromEventDict(eventDict)

        if text is None:
            return

        # skip annoying twisted messages
        if text in [ 'Log opened.', 'Main loop terminated.' ]:
            return

        text += "\n"
        self.write(text)
        self.flush()

