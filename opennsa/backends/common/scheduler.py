"""
Connection state scheduler

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

import datetime

from twisted.python import log
from twisted.internet import reactor, defer, task



LOG_SYSTEM = 'opennsa.Scheduler'



def deferTaskFailed(err):
    if err.check(defer.CancelledError):
        pass # this just means that the task was cancelled
    else:
        log.err(err)
        return err



class TransitionScheduler:

    def __init__(self):
        self.scheduled_transition_call = None


    def scheduleTransition(self, transition_time, call, state):

        assert self.scheduled_transition_call is None or self.scheduled_transition_call.called is True, 'Scheduling transition while other transition is scheduled'

        dt_now = datetime.datetime.utcnow()

        # allow a bit leeway in transition to avoid odd race conditions
        assert transition_time >= (dt_now - datetime.timedelta(seconds=1)), 'Scheduled transition is not in the future (%s >= %s is False)' % (transition_time, dt_now)

        td = (transition_time - dt_now)
        transition_delta_seconds = (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6.0
        transition_delta_seconds = max(transition_delta_seconds, 0) # if dt_now is passed during calculation

        d = task.deferLater(reactor, transition_delta_seconds, call, state)
        d.addErrback(deferTaskFailed)
        self.scheduled_transition_call = d
        log.msg('State transition scheduled: In %i seconds to state %s' % (transition_delta_seconds, state), system=LOG_SYSTEM)
        return d


    def cancelTransition(self):

        if self.scheduled_transition_call:
            self.scheduled_transition_call.cancel()
            self.scheduled_transition_call = None

