"""
Simple log observer for the OpenNSA CLI util.
"""

from twisted.python import log



class SimpleObserver(log.FileLogObserver):

    first_line = True
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
        if self.first_line and text == 'Log opened.':
            return # skip annoying twisted message

        text += "\n"
        self.write(text)
        self.flush()

        self.first_line = False

