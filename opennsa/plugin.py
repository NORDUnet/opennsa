import string
import random

from zope.interface import implements

from twisted.internet import defer

from opennsa.interface import IPlugin
from opennsa import config



class BasePlugin:
    implements(IPlugin)

    """
    Default plugin.

    Can be used to inherint from so only relevant methods have to be defined in custom
    plugins. Also used as default, so we don't have to check to see if a plugin exists
    before calling.
    """

    def init(self, cfg, ctx_factory):
        self.cfg         = cfg
        self.ctx_factory = ctx_factory

        self.conn_prefix = cfg[config.NETWORK_NAME][:2].upper() + '-'


    def connectionRequest(self, header, connection_id, global_reservation_id, description, criteria):
        return defer.succeed(None)


    def createConnectionId(self):
        connection_id = self.conn_prefix + ''.join( [ random.choice(string.hexdigits[:16]) for _ in range(10) ] )
        return defer.succeed(connection_id)


    def prunePaths(self, paths):
        return defer.succeed(paths)


    def connectionCreated(self, connection):
        return defer.succeed(None)


    def connectionTerminated(self, connection):
        return defer.succeed(None)

