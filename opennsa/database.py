"""
Database module.

The module is based on Twistar (http://findingscience.com/twistar/), which is an ORM.

Only supported database is PostgreSQL for now.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2013)
"""

import datetime

from twisted.enterprise import adbapi

from psycopg2.extensions import adapt, register_adapter, AsIs
from psycopg2.extras import CompositeCaster, register_composite

from twistar.registry import Registry
from twistar.dbobject import DBObject

from opennsa import nsa
from opennsa.ext.iso8601 import iso8601



LOG_SYSTEM = 'opennsa.Database'


# psycopg2 plumming to get automatic adaption
def adaptLabel(label):
    return AsIs("(%s, %s)::label" % (adapt(label.type_), adapt(label.labelValue())))

def adaptSecuritAttribute(label):
    return AsIs("(%s, %s)::security_attribute" % (adapt(label.type_), adapt(label.value)))

def adaptDatetime(dt):
    return AsIs("%s" % adapt(dt.isoformat()))


register_adapter(nsa.Label, adaptLabel)
register_adapter(nsa.SecurityAttribute, adaptSecuritAttribute)
register_adapter(datetime.datetime, adaptDatetime)


class LabelComposite(CompositeCaster):
    def make(self, values):
        return nsa.Label(*values)


class SecuritAttributeComposite(CompositeCaster):
    def make(self, values):
        return nsa.SecurityAttribute(*values)


def castDatetime(value, cur):
    return iso8601.parse(value)


# setup

def setupDatabase(database, user, password=None, connection_id_start=None):

    # hack on, use psycopg2 connection to register postgres label -> nsa label adaptation
    import psycopg2
    conn = psycopg2.connect(user=user, password=password, database=database)
    cur = conn.cursor()
    register_composite('label', cur, globally=True, factory=LabelComposite)
    register_composite('security_attribute', cur, globally=True, factory=SecuritAttributeComposite)

    cur.execute("SELECT oid FROM pg_type WHERE typname = 'timestamptz';")
    timestamptz_oid = cur.fetchone()[0]

    DT = psycopg2.extensions.new_type((timestamptz_oid,), "timestamptz", castDatetime)
    psycopg2.extensions.register_type(DT)

    if connection_id_start:
        cur.execute("INSERT INTO backend_connection_id (connection_id) VALUES (%s) ON CONFLICT DO NOTHING;", connection_id_start)

    conn.close()

    Registry.DBPOOL = adbapi.ConnectionPool('psycopg2', user=user, password=password, database=database)






# ORM Objects

class ServiceConnection(DBObject):
    HASMANY = ['SubConnections']


class SubConnection(DBObject):
    BELONGSTO = ['ServiceConnection']


class STPAuthz(DBObject):
    TABLENAME = 'stp_authz'


# Not really needed
class BackendConnectionID(DBObject):
    TABLENAME = 'backend_connection_id'

#@defer.inlineCallbacks
def getBackendConnectionId():

#    rows = yield BackendConnectionID.find()
#    if len(rows) == 0:
#        defer.returnValue(0)
#    else:
#        connection_id = rows[0].connection_id
#        rows[0].connection_id += 1
#        rows[0].save()
#        defer.returnValue(connection_id)

    def gotResult(rows):
        print 'rows', rows
        if len(rows) == 0:
            return None
        else:
            return rows[0][0]

    return Registry.DBPOOL.runQuery('UPDATE backend_connection_id SET connection_id = connection_id + 1 RETURNING connection_id;').addCallback(gotResult)



Registry.register(ServiceConnection, SubConnection)

