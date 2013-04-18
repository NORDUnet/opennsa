"""
Database module.

The module is based on Twistar (http://findingscience.com/twistar/), which is an ORM.

Only supported database is PostgreSQL for now.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2011-2013)
"""

from twisted.enterprise import adbapi

from psycopg2.extensions import adapt, register_adapter, AsIs
from twistar.registry import Registry
from twistar.dbobject import DBObject

from opennsa import nsa



LOG_SYSTEM = 'opennsa.Database'


# psycopg2 plumming to get automatic adaption
def adaptLabel(label):
    return AsIs("(%s, %s)::label" % (adapt(label.type_), adapt(label.labelValue)))

register_adapter(nsa.Label, adaptLabel)



# setup

def setupDatabase(user, password, database):

    Registry.DBPOOL = adbapi.ConnectionPool('psycopg2', user=user, password=password, database=database)



# ORM Objects

class Connection(DBObject):
    HASMANY = ['subconnections']


class SubConnection(DBObject):
    BELONGSTO = ['connection']

