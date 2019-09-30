"""
NSI state machine.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011)
"""

from twisted.python import log

from opennsa import error


LOG_SYSTEM = 'opennsa.state'


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

# The PROVISIONING -> PROVISIONING  and RELEASING -> RELEASING transitions
# isn't canon, but is needed in case a provision/release request and fails due
# to pre-check or similar. The provisoning/release request can be recovered by
# sending down a second provision request. This can happen in cases of authZ
# check, error to activate/deactive data plane or similar.

PROVISION_TRANSITIONS = {
    RELEASED        : [ PROVISIONING  ],
    PROVISIONING    : [ PROVISIONING,   PROVISIONED   ],
    PROVISIONED     : [ RELEASING     ],
    RELEASING       : [ RELEASING,      RELEASED      ]
}

LIFECYCLE_TRANSITIONS = {
    CREATED         : [ FAILED, PASSED_ENDTIME, TERMINATING, TERMINATED ],
    FAILED          : [ TERMINATING ],
    PASSED_ENDTIME  : [ TERMINATING ],
    TERMINATING     : [ TERMINATING, TERMINATED ],
    TERMINATED      : []
}

SUBSCRIPTIONS = {}

def subscribe(connection_id, f):
    global SUBSCRIPTIONS
    SUBSCRIPTIONS.setdefault(connection_id, []).append(f)

def desubscribe(connection_id, f):
    SUBSCRIPTIONS[connection_id].remove(f)


def saveNotify(conn):

    def notify(conn):
        try:
            for f in SUBSCRIPTIONS[conn.connection_id]:
                try:
                    f()
                except Exception as e:
                    log.msg('Error during state notificaton: %s' % str(e), system=LOG_SYSTEM)
        except KeyError:
            #print('Nothing to notify about {}'.format(conn.connection_id))
            pass

        return conn

    d = conn.save()
    d.addCallback(notify)
    return d


def _switchState(transition_schema, old_state, new_state):
    if new_state in transition_schema[old_state]:
        return
    else:
        raise error.InternalServerError('Transition from state %s to %s not allowed' % (old_state, new_state))

# Reservation


def reserveChecking(conn):
    _switchState(RESERVE_TRANSITIONS, conn.reservation_state, RESERVE_CHECKING)
    conn.reservation_state = RESERVE_CHECKING
    return saveNotify(conn)

def reserveHeld(conn):
    _switchState(RESERVE_TRANSITIONS, conn.reservation_state, RESERVE_HELD)
    conn.reservation_state = RESERVE_HELD
    return saveNotify(conn)

def reserveFailed(conn):
    _switchState(RESERVE_TRANSITIONS, conn.reservation_state, RESERVE_FAILED)
    conn.reservation_state = RESERVE_FAILED
    return saveNotify(conn)

def reserveCommit(conn):
    _switchState(RESERVE_TRANSITIONS, conn.reservation_state, RESERVE_COMMITTING)
    conn.reservation_state = RESERVE_COMMITTING
    return saveNotify(conn)

def reserveAbort(conn):
    _switchState(RESERVE_TRANSITIONS, conn.reservation_state, RESERVE_ABORTING)
    conn.reservation_state = RESERVE_ABORTING
    return saveNotify(conn)

def reserveTimeout(conn):
    _switchState(RESERVE_TRANSITIONS, conn.reservation_state, RESERVE_TIMEOUT)
    conn.reservation_state = RESERVE_TIMEOUT
    return saveNotify(conn)

def reserved(conn):
    _switchState(RESERVE_TRANSITIONS, conn.reservation_state, RESERVE_START)
    conn.reservation_state = RESERVE_START
    return saveNotify(conn)

def reserveMultiSwitch(conn, *states):
    # switch through multiple states in one go, note this does not save the state (because it is often needed with allocation switch)
    for s in states:
        _switchState(RESERVE_TRANSITIONS, conn.reservation_state, s)
        conn.reservation_state = s
    return saveNotify(conn)


# Provision

def provisioning(conn):
    _switchState(PROVISION_TRANSITIONS, conn.provision_state, PROVISIONING)
    conn.provision_state = PROVISIONING
    return saveNotify(conn)

def provisioned(conn):
    _switchState(PROVISION_TRANSITIONS, conn.provision_state, PROVISIONED)
    conn.provision_state = PROVISIONED
    return saveNotify(conn)

def releasing(conn):
    _switchState(PROVISION_TRANSITIONS, conn.provision_state, RELEASING)
    conn.provision_state = RELEASING
    return saveNotify(conn)

def released(conn):
    _switchState(PROVISION_TRANSITIONS, conn.provision_state, RELEASED)
    conn.provision_state = RELEASED
    return saveNotify(conn)

# Lifecyle

def passedEndtime(conn):
    _switchState(LIFECYCLE_TRANSITIONS, conn.lifecycle_state, PASSED_ENDTIME)
    conn.lifecycle_state = PASSED_ENDTIME
    return saveNotify(conn)

def failed(conn):
    _switchState(LIFECYCLE_TRANSITIONS, conn.lifecycle_state, FAILED)
    conn.lifecycle_state = FAILED
    return saveNotify(conn)

def terminating(conn):
    _switchState(LIFECYCLE_TRANSITIONS, conn.lifecycle_state, TERMINATING)
    conn.lifecycle_state = TERMINATING
    return saveNotify(conn)

def terminated(conn):
    _switchState(LIFECYCLE_TRANSITIONS, conn.lifecycle_state, TERMINATED)
    conn.lifecycle_state = TERMINATED
    return saveNotify(conn)

