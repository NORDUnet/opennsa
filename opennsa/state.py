"""
NSI state machine.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from opennsa import error



# connection states
INITIAL                 = 'Initial'             # R, P, A

RESERVING               = 'Reserving'           # R,
RESERVED                = 'Reserved'            # R
RESERVE_FAILED          = 'ReserveFailed'       # R

MODIFY_CHECKING         = 'ModifyChecking'      # R
MODIFY_CHECHED          = 'ModifyChecked'       # R
MODIFY_CHECK_FAILED     = 'ModifyCheckFailed'   # R

MODIFY_CANCELING        = 'ModifyCanceling'     # R
MODIFY_CANCEL_FAILED    = 'ModifyCancelFailed'  # R

MODIFYING               = 'Modifying'           # R
MODIFY_FAILED           = 'ModifyFailed'        # R

SCHEDULED               = 'Scheduled'           #   P
PROVISIONING            = 'Provisioning'        #   P
PROVISIONED             = 'Provisioned'         #   P
PROVISION_FAILED        = 'ProvisionFailed'     #   P

RELEASING               = 'Releasing'           #   P
RELEASE_FAILED          = 'ReleaseFailed'       #   P

TERMINATING             = 'Terminating'         # R, P
TERMINATED_RESERVED     = 'TerminatedReserved'  # R, P
TERMINATED_ENDTIME      = 'TerminatedEndtime'   # R, P
TERMINATED_REQUEST      = 'TerminatedRequest'   # R, P
TERMINATED_FAILED       = 'TerminateFailed'     # R, P

INACTIVE                = 'Inactive'            #       A
ACTIVATING              = 'Activating'          #       A
ACTIVE                  = 'Active'              #       A
DEACTIVATING            = 'Deactivating'        #       A

UNKNOWN                 = 'Unknown'             # R, P, A - Lets try not to use this one, mkay

# lists
TERMINATED_STATES       = [ TERMINATED_RESERVED, TERMINATED_ENDTIME, TERMINATED_REQUEST, TERMINATED_FAILED ]

# These are deprecated
TERMINATED              = 'Terminated'
CLEANING                = 'Cleaning'


# We don't support modify yet, so those are not in there yet
RESERVE_TRANSITIONS = {
    INITIAL         : [ RESERVING                                                                       ],
    RESERVING       : [ RESERVED,       RESERVE_FAILED                                                  ],
    RESERVED        : [ TERMINATING                                                                     ],
    TERMINATING     : [ TERMINATED_RESERVED, TERMINATED_ENDTIME, TERMINATED_REQUEST, TERMINATED_FAILED  ]
}


PROVISION_TRANSITIONS = {
    INITIAL         : [ SCHEDULED,                             TERMINATING                              ],
    SCHEDULED       : [ PROVISIONING,                          TERMINATING                              ],
    PROVISIONING    : [ PROVISIONED,  SCHEDULED,               TERMINATING                              ],
    PROVISIONED     : [ RELEASING,    PROVISIONING,            TERMINATING                              ],
    RELEASING       : [ SCHEDULED,                             TERMINATING                              ],
    TERMINATING     : [ TERMINATED_RESERVED, TERMINATED_ENDTIME, TERMINATED_REQUEST, TERMINATED_FAILED  ]
}

ACTIVATION_TRANSITIONS = {
    INACTIVE        : [ ACTIVATING              ],
    ACTIVATING      : [ ACTIVE,      INACTIVE   ],
    ACTIVE          : [ DEACTIVATING            ],
    DEACTIVATING    : [ INACTIVE                ]
}


class AbstractStateMachine:

    TRANSITIONS = None

    def __init__(self):
        raise AssertionError('Should not be instantiated')

    def __call__(self):
        return self.state()


    def state(self):
        return self._state


    def switchState(self, new_state):
        if new_state in self.TRANSITIONS[self._state]:
            self._state = new_state
        else:
            raise error.InternalServerError('Transition from state %s to %s not allowed' % (self._state, new_state))



class ReservationState(AbstractStateMachine):

    TRANSITIONS = RESERVE_TRANSITIONS

    def __init__(self, state=INITIAL):
        self._state = state



class ProvisionState(AbstractStateMachine):

    TRANSITIONS = PROVISION_TRANSITIONS

    def __init__(self, state=INITIAL):
        self._state = state



class ActivationState(AbstractStateMachine):

    TRANSITIONS = ACTIVATION_TRANSITIONS

    def __init__(self, state=INACTIVE):
        self._state = state



class NSI2StateMachine:
    # high-level state machine acting as a facade to the three actual state machines

    def __init__(self):
        self.reservation_state  = ReservationState()
        self.provision_state    = ProvisionState()
        self.activation_state   = ActivationState()

    def reserving(self):
        self.reservation_state.switchState(RESERVING)

    def reserved(self):
        self.reservation_state.switchState(RESERVED)
        self.provision_state.switchState(SCHEDULED)

    def scheduled(self):
        # not sure this one is needed
        self.provision_state.switchState(SCHEDULED)

    def provisioning(self):
        self.provision_state.switchState(PROVISIONING)

    def provisioned(self):
        self.provision_state.switchState(PROVISIONED)

    def releasing(self):
        self.provision_state.switchState(RELEASING)

    def released(self):
        self.provision_state.switchState(SCHEDULED)

    def activating(self):
        self.activation_state.switchState(ACTIVATING)

    def active(self):
        self.activation_state.switchState(ACTIVE)

    def deactivating(self):
        self.activation_state.switchState(DEACTIVATING)

    def inactive(self):
        self.activation_state.switchState(INACTIVE)

    def terminating(self):
        self.reservation_state.switchState(TERMINATING)
        self.provision_state.switchState(TERMINATING)

    def terminatedEndtime(self):
        self.reservation_state.switchState(TERMINATED_ENDTIME)
        self.provision_state.switchState(TERMINATED_ENDTIME)

    def terminatedRequest(self):
        self.reservation_state.switchState(TERMINATED_REQUEST)
        self.provision_state.switchState(TERMINATED_REQUEST)

    def terminatedFailed(self):
        self.reservation_state.switchState(TERMINATED_ENDTIME)
        self.provision_state.switchState(TERMINATED_ENDTIME)

    # queries

    def isActive(self):
        return self.activation_state() == ACTIVE

    def isTerminated(self):
        return self.reservation_state() in TERMINATED_STATES and self.provision_state() in TERMINATED_STATES

