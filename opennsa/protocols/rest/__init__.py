
from . import resource

CONNECTIONS = b'connections'
PATH = '/' + CONNECTIONS.decode('utf-8')

def setupService(provider, top_resource, allowed_hosts=None):

    r = resource.P2PBaseResource(provider, PATH, allowed_hosts)

    top_resource.putChild(CONNECTIONS, r)

