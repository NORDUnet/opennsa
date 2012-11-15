"""
Simple log observer for the OpenNSA CLI util.
"""

from twisted.python import log



class SimpleObserver(log.FileLogObserver):

    debug = False
    dump_payload = False

    def emit(self, eventDict):

        if 'debug' in eventDict and eventDict['debug']:
            if not self.debug:
                return # skip this message if we do not want debug

        if 'payload' in eventDict and eventDict['payload']:
            if not self.dump_payload:
                return # skip this message if we do not want debug

        text = log.textFromEventDict(eventDict)

        if text is None:
            return

        # skip annoying twisted messages
        if text in [ 'Log opened.', 'Main loop terminated.' ]:
            return
        if text.startswith('twisted.web.server.Site starting on') or \
           text.startswith('Starting factory <twisted.web.server.Site instance') or \
           text.startswith('Stopping factory <twisted.web.server.Site instance'):
            return

        text += "\n"
        self.write(text)
        self.flush()

