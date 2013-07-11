"""
NSI state machine.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from opennsa import error



# Reservation states
RESERVE_START           = 'ReserveStart'
RESERVE_CHECKING        = 'ReserveChecking'
RESERVE_HELD            = 'ReserveHeld'
RESERVE_COMMITTING      = 'ReserveComitting'
RESERVE_FAILED          = 'ReserveFailed'
RESERVE_ABORTING        = 'ReserveAborting'
RESERVE_TIMEOUT         = 'ReserveTimeout'      # Only UPA

# Provision
RELEASED                = 'Released'
PROVISIONING            = 'Provisioning'
PROVISIONED             = 'Provisioned'
RELEASING               = 'Releasing'

# Lifecycle
CREATED                 = 'Created'
FAILED                  = 'Failed'
PASSED_ENDTIME          = 'PassedEndTime'
TERMINATING             = 'Terminating'
TERMINATED              = 'Terminated'


RESERVE_TRANSITIONS = {
    RESERVE_START       : [ RESERVE_CHECKING                                       ],
    RESERVE_CHECKING    : [ RESERVE_HELD,       RESERVE_FAILED                     ],
    RESERVE_HELD        : [ RESERVE_COMMITTING, RESERVE_ABORTING, RESERVE_TIMEOUT  ],
    RESERVE_COMMITTING  : [ RESERVE_START                                          ],
    RESERVE_FAILED      : [ RESERVE_ABORTING                                       ],
    RESERVE_TIMEOUT     : [ RESERVE_ABORTING                                       ],
    RESERVE_ABORTING    : [ RESERVE_START                                          ]
}

PROVISION_TRANSITIONS = {
    RELEASED        : [ PROVISIONING  ],
    PROVISIONING    : [ PROVISIONED   ],
    PROVISIONED     : [ RELEASING     ],
    RELEASING       : [ RELEASED      ]
}

LIFECYCLE_TRANSITIONS = {
    CREATED         : [ FAILED, PASSED_ENDTIME, TERMINATING, TERMINATED ],
    FAILED          : [ TERMINATING ],
    PASSED_ENDTIME  : [ TERMINATING ],
    TERMINATING     : [ TERMINATED ],
    TERMINATED      : []
}


def _switchState(transition_schema, old_state, new_state):
    if new_state in transition_schema[old_state]:
        return
    else:
        raise error.InternalServerError('Transition from state %s to %s not allowed' % (old_state, new_state))

# Reservation


def reserveChecking(conn):
    _switchState(RESERVE_TRANSITIONS, conn.reservation_state, RESERVE_CHECKING)
    conn.reservation_state = RESERVE_CHECKING
    return conn.save()

def reserveHeld(conn):
    _switchState(RESERVE_TRANSITIONS, conn.reservation_state, RESERVE_HELD)
    conn.reservation_state = RESERVE_HELD
    return conn.save()

def reserveCommit(conn):
    _switchState(RESERVE_TRANSITIONS, conn.reservation_state, RESERVE_COMMITTING)
    conn.reservation_state = RESERVE_COMMITTING
    return conn.save()

def reserveAbort(conn):
    _switchState(RESERVE_TRANSITIONS, conn.reservation_state, RESERVE_ABORTING)
    conn.reservation_state = RESERVE_ABORTING
    return conn.save()

def reserveTimeout(conn):
    _switchState(RESERVE_TRANSITIONS, conn.reservation_state, RESERVE_TIMEOUT)
    conn.reservation_state = RESERVE_TIMEOUT
    return conn.save()

def reserved(conn):
    _switchState(RESERVE_TRANSITIONS, conn.reservation_state, RESERVE_START)
    conn.reservation_state = RESERVE_START
    return conn.save()

# Provision

def provisioning(conn):
    _switchState(PROVISION_TRANSITIONS, conn.provision_state, PROVISIONING)
    conn.provision_state = PROVISIONING
    return conn.save()

def provisioned(conn):
    _switchState(PROVISION_TRANSITIONS, conn.provision_state, PROVISIONED)
    conn.provision_state = PROVISIONED
    return conn.save()

def releasing(conn):
    _switchState(PROVISION_TRANSITIONS, conn.provision_state, RELEASING)
    conn.provision_state = RELEASING
    return conn.save()

def released(conn):
    _switchState(PROVISION_TRANSITIONS, conn.provision_state, RELEASED)
    conn.provision_state = RELEASED
    return conn.save()

# Lifecyle

def passedEndtime(conn):
    _switchState(LIFECYCLE_TRANSITIONS, conn.lifecycle_state, PASSED_ENDTIME)
    conn.lifecycle_state = PASSED_ENDTIME
    return conn.save()

def failed(conn):
    _switchState(LIFECYCLE_TRANSITIONS, conn.lifecycle_state, FAILED)
    conn.lifecycle_state = FAILED
    return conn.save()

def terminating(conn):
    _switchState(LIFECYCLE_TRANSITIONS, conn.lifecycle_state, TERMINATING)
    conn.lifecycle_state = TERMINATING
    return conn.save()

def terminated(conn):
    _switchState(LIFECYCLE_TRANSITIONS, conn.lifecycle_state, TERMINATED)
    conn.lifecycle_state = TERMINATED
    return conn.save()

