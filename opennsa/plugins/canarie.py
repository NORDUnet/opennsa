"""
Plugin for Canarie specific behaviour in OpenNSA.

It creates connection ids to match the Canarie circuit id specification

Author: Henrik Thostrup Jensen < htj at nordu dot net >
Copyright: NORDUnet A/S (2017)
"""

from zope.interface import implements

from twisted.internet import defer
from twisted.python import log

from opennsa import database, plugin
from opennsa.interface import IPlugin



LOG_SYSTEM = 'Canarie'


class CanariePlugin(plugin.BasePlugin):
    implements(IPlugin)

    @defer.inlineCallbacks
    def createConnectionId(self):
        """
        Create a Canarie service identifier for the connection.
        """
        unique_id = yield database.getBackendConnectionId()
        if unique_id is None:
            raise ValueError("Could not generate an connection id from the database, most likely serviceid_start isn't set")

        unique_id = str(unique_id)

        connection_id = unique_id[:5] + 'CS' + unique_id[5:] + '-ANA'
        log.msg('Generated id: ' + connection_id, system=LOG_SYSTEM)
        defer.returnValue(connection_id)


plugin = CanariePlugin()

