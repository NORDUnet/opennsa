"""
NSI state machine.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from opennsa import error



# connection states
INITIAL             = 'Initial'

RESERVING           = 'Reserving'
RESERVED            = 'Reserved'

SCHEDULED           = 'Scheduled'
AUTO_PROVISION      = 'Auto-Provision'
PROVISIONING        = 'Provisioning'
PROVISIONED         = 'Provisioned'

RELEASING           = 'Releasing'
CLEANING            = 'Cleaning'

TERMINATING         = 'Terminating'
TERMINATED          = 'Terminated'

# allowed state transitions
# the scheduled -> auto provision is not canon, but AFAICT it should be okay
TRANSITIONS = {
    INITIAL         : [ RESERVING                                                               ],
    RESERVING       : [ RESERVED,       TERMINATING,    CLEANING,     TERMINATED                ],
    RESERVED        : [ SCHEDULED,      AUTO_PROVISION, PROVISIONING, TERMINATING, TERMINATED   ],
    SCHEDULED       : [ AUTO_PROVISION, PROVISIONING,   RELEASING,    TERMINATING, TERMINATED   ],
    AUTO_PROVISION  : [ PROVISIONING,   TERMINATING,    TERMINATED                              ],
    PROVISIONING    : [ PROVISIONED,    TERMINATING,    TERMINATED                              ],
    PROVISIONED     : [ RELEASING,      TERMINATING,    TERMINATING,                            ],
    RELEASING       : [ RESERVED,       SCHEDULED,      TERMINATING,    TERMINATED              ],
    CLEANING        : [ TERMINATED                                                              ],
    TERMINATING     : [ TERMINATED,                                                             ],
    TERMINATED      : [ ]
}



class ConnectionState:

    def __init__(self, state=INITIAL):
        self._state = state


    def __call__(self):
        return self.state()


    def state(self):
        return self._state


    def switchState(self, new_state):
        if new_state in TRANSITIONS[self._state]:
            self._state = new_state
        else:
            raise error.StateTransitionError('Transition from state %s to %s not allowed' % (self._state, new_state))

