"""
Database module.

The module is based on Twistar (http://findingscience.com/twistar/), which is an ORM.

Only supported database is PostgreSQL for now.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2013)
"""

import datetime
from dateutil import parser

from twisted.enterprise import adbapi

from psycopg2.extensions import adapt, register_adapter, AsIs
from psycopg2.extras import CompositeCaster, register_composite

from twistar.registry import Registry
from twistar.dbobject import DBObject

from opennsa import nsa



LOG_SYSTEM = 'opennsa.Database'


# psycopg2 plumming to get automatic adaption
def adaptLabel(label):
    return AsIs("(%s, %s)::label" % (adapt(label.type_), adapt(label.labelValue())))

def adaptDatetime(dt):
    return AsIs("%s" % adapt(dt.isoformat()))


register_adapter(nsa.Label, adaptLabel)
register_adapter(datetime.datetime, adaptDatetime)


class LabelComposite(CompositeCaster):
    def make(self, values):
        return nsa.Label(*values)


def castDatetime(value, cur):
    return parser.parse(value)


# setup

def setupDatabase(database, user, password=None):

    # hack on, use psycopg2 connection to register postgres label -> nsa label adaptation
    import psycopg2
    conn = psycopg2.connect(user=user, password=password, database=database)
    cur = conn.cursor()
    register_composite('label', cur, globally=True, factory=LabelComposite)

    cur.execute("SELECT oid FROM pg_type WHERE typname = 'timestamptz';")
    timestamptz_oid = cur.fetchone()[0]

    DT = psycopg2.extensions.new_type((timestamptz_oid,), "timestamptz", castDatetime)
    psycopg2.extensions.register_type(DT)

    conn.close()

    Registry.DBPOOL = adbapi.ConnectionPool('psycopg2', user=user, password=password, database=database)




# ORM Objects

class ServiceConnection(DBObject):
    HASMANY = ['SubConnections']


class SubConnection(DBObject):
    BELONGSTO = ['ServiceConnection']


Registry.register(ServiceConnection, SubConnection)

