"""
Call scheduler. Handles one future call per connection.

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



class CallScheduler:

    def __init__(self):
        self.scheduled_calls = {}
        self.clock = reactor # this is needed in order to test scheduled calls


    def scheduleCall(self, connection_id, transition_time, call, *args):
        assert callable(call), 'call argument is not a callable'

        try:
            sched_call = self.scheduled_calls[connection_id]
            assert sched_call.called is True, 'Connection %s: Attempt to schedule transition with existing schedule transition' % connection_id
        except KeyError:
            pass # no scheduled call

        dt_now = datetime.datetime.utcnow()

        # allow a bit leeway in transition to avoid odd race conditions
        assert transition_time >= (dt_now - datetime.timedelta(seconds=1)), 'Scheduled transition is not in the future (%s >= %s is False)' % (transition_time, dt_now)

        td = (transition_time - dt_now)
        transition_delta_seconds = (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6.0
        transition_delta_seconds = max(transition_delta_seconds, 0) # if dt_now is passed during calculation

        d = task.deferLater(self.clock, transition_delta_seconds, call, *args)
        d.addErrback(deferTaskFailed)
        self.scheduled_calls[connection_id] = d
        return d


    def hasScheduledCall(self, connection_id):
        return connection_id in self.scheduled_calls


    def cancelCall(self, connection_id):
        try:
            sched_call = self.scheduled_calls.pop(connection_id)
            sched_call.cancel()
        except KeyError:
            pass


    def cancelAllCalls(self):
        for k in self.scheduled_calls.keys():
            self.scheduled_calls.pop(k).cancel()

