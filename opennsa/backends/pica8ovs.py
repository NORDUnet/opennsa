"""
OpenNSA Pica8 OVS backend.

Authors:  iCAIR. Contributions by SURFnet, NORDUnet

"""

import random

from twisted.python import log
from twisted.internet import defer

from opennsa import constants as cnt, config
from opennsa.backends.common import ssh, genericbackend

LOG_SYSTEM = 'opennsa.pica8ovs'

# parameterized commands
COMMAND_ECHO            = 'echo'

# Substitute switch IP and TCP port
COMMAND_SET_INTERFACE_VLAN      = '/ovs/bin/ovs-vsctl --db=tcp:%s:6640 add port %s trunk %i'
COMMAND_DELETE_INTERFACE_VLAN   = '/ovs/bin/ovs-vsctl --db=tcp:%s:6640 remove port %s trunk %i'

COMMAND_ADD_FLOW                = '/ovs/bin/ovs-ofctl add-flow br0 in_port=%s,dl_vlan=%i,actions=output:%s'
COMMAND_ADD_FLOW_SWAP           = '/ovs/bin/ovs-ofctl add-flow br0 in_port=%s,dl_vlan=%i,action=set_field=%i-\\>vlan_vid,output:%s'
COMMAND_DELETE_FLOW             = '/ovs/bin/ovs-ofctl del-flows br0 in_port=%s,dl_vlan=%i'


def createConfigureCommands(db_ip, source_nrm_port, dest_nrm_port, source_vlan, dest_vlan):

    cmd_s_intf  = COMMAND_SET_INTERFACE_VLAN % (db_ip, source_nrm_port, source_vlan)
    cmd_d_intf  = COMMAND_SET_INTERFACE_VLAN % (db_ip, dest_nrm_port, dest_vlan)
    s_flow = str(int(source_nrm_port.split('/')[2]) + 128)
    d_flow = str(int(dest_nrm_port.split('/')[2]) + 128)
    if source_vlan == dest_vlan:
        cmd_s_flow  = COMMAND_ADD_FLOW              % ( s_flow, source_vlan, d_flow )
        cmd_d_flow  = COMMAND_ADD_FLOW              % ( d_flow, source_vlan, s_flow )
    else:
        cmd_s_flow  = COMMAND_ADD_FLOW_SWAP         % ( s_flow, source_vlan, dest_vlan, d_flow )
        cmd_d_flow  = COMMAND_ADD_FLOW_SWAP         % ( d_flow, dest_vlan, source_vlan, s_flow )

    commands = [ cmd_s_intf, cmd_d_intf, cmd_s_flow, cmd_d_flow ]
    return commands


def createDeleteCommands(db_ip, source_nrm_port, dest_nrm_port, source_vlan, dest_vlan):

    cmd_no_s_intf = COMMAND_DELETE_INTERFACE_VLAN % (db_ip, source_nrm_port, source_vlan )
    cmd_no_d_intf = COMMAND_DELETE_INTERFACE_VLAN % (db_ip, dest_nrm_port, dest_vlan )
    s_flow = str(int(source_nrm_port.split('/')[2]) + 128)
    d_flow = str(int(dest_nrm_port.split('/')[2]) + 128)
    cmd_no_s_flow = COMMAND_DELETE_FLOW         % ( s_flow, source_vlan )
    cmd_no_d_flow = COMMAND_DELETE_FLOW         % ( d_flow, dest_vlan )

    commands = [ cmd_no_s_flow, cmd_no_d_flow, cmd_no_s_intf, cmd_no_d_intf ]
    return commands


class SSHChannel(ssh.SSHChannel):

    name = 'session'

    def __init__(self, conn):
        ssh.SSHChannel.__init__(self, conn=conn)

        self.data = ''

        self.wait_defer = None
        self.wait_data  = None


    @defer.inlineCallbacks
    def sendCommands(self, commands):
        LT = '\n' # line termination

        try:
            yield self.conn.sendRequest(self, 'shell', '', wantReply=1)

#            time.sleep(1) # FIXME
            d = self.waitForData('\n')
            self.write(COMMAND_ECHO + LT)
            yield d

            log.msg('Ready', debug=True, system=LOG_SYSTEM)

            for cmd in commands:
                log.msg('CMD> %s' % cmd, system=LOG_SYSTEM)
                d = self.waitForData('\n')
                self.write(cmd + LT)
                self.write(COMMAND_ECHO + LT)
#                time.sleep(1) # FIXME
                yield d

            # commit commands, check for 'commit complete' as success
            # not quite sure how to handle failure here

            ## test stuff
            #d = self.waitForData('[edit]')
            #self.write('commit check' + LT)

            #d = self.waitForData('commit complete')
            #self.write(COMMAND_COMMIT + LT)
            #yield d

        except Exception as e:
            log.msg('Error sending commands: %s' % str(e))
            raise e

        d = self.waitForData('\n')
        self.write(COMMAND_ECHO + LT)
        yield d
        log.msg('Commands successfully sent', system=LOG_SYSTEM)
        self.sendEOF()
        self.closeIt()


    def waitForData(self, data):
        self.wait_data  = data
        self.wait_defer = defer.Deferred()
        return self.wait_defer


    def dataReceived(self, data):
        if len(data) == 0:
            pass
        else:
            self.data += data
            if self.wait_data and self.wait_data in self.data:
                d = self.wait_defer
                self.data       = ''
                self.wait_data  = None
                self.wait_defer = None
                d.callback(self)


class Pica8OVSCommandSender:


    def __init__(self, host, port, ssh_host_fingerprint, user, ssh_public_key_path, ssh_private_key_path, db_ip):

        self.ssh_connection_creator = \
             ssh.SSHConnectionCreator(host, port, [ ssh_host_fingerprint ], user, ssh_public_key_path, ssh_private_key_path)
        self.db_ip = db_ip

        log.msg('SSH connection arguments %s, %s, %s, %s, %s, %s' % (host, port, ssh_host_fingerprint, user, ssh_public_key_path, ssh_private_key_path), system=LOG_SYSTEM)


    @defer.inlineCallbacks
    def _sendCommands(self, commands):

        log.msg('Creating new SSH connection', system=LOG_SYSTEM)

        ssh_connection = yield self.ssh_connection_creator.getSSHConnection()

        try:
            ssh_channel = SSHChannel(conn = ssh_connection)
            ssh_connection.openChannel(ssh_channel)
            yield ssh_channel.channel_open
            yield ssh_channel.sendCommands(commands)
            # not a yield, just being nice
            ssh_channel.loseConnection()

        finally:
            # twisted/os will flush data, before closing
            ssh_connection.transport.loseConnection()


    def setupLink(self, source_target, dest_target):

        commands = createConfigureCommands(self.db_ip, source_target.port, dest_target.port, source_target.vlan, dest_target.vlan)
        return self._sendCommands(commands)


    def teardownLink(self, source_target, dest_target):

        commands = createDeleteCommands(self.db_ip, source_target.port, dest_target.port, source_target.vlan, dest_target.vlan)
        return self._sendCommands(commands)


# --------


class Pica8OVSTarget(object):

    def __init__(self, port, vlan=None):
        self.port = port
        self.vlan = vlan

    def __str__(self):
        if self.vlan:
            return '<Pica8OVSTarget %s#%i>' % (self.port, self.vlan)
        else:
            return '<Pica8OVSTarget %s>' % self.port



class Pica8OVSConnectionManager:

    def __init__(self, port_map, host, port, host_fingerprint, user, ssh_public_key, ssh_private_key, db_ip):

        self.port_map = port_map
        self.command_sender = Pica8OVSCommandSender(host, port, host_fingerprint, user, ssh_public_key, ssh_private_key, db_ip)


    def getResource(self, port, label):
        assert label is not None or label.type_ == cnt.ETHERNET_VLAN, 'Label type must be VLAN'
        # resource is port + vlan (router / virtual switching)
        label_value = '' if label is None else label.labelValue()
        return port + ':' + label_value


    def getTarget(self, port, label):
        assert label is not None and label.type_ == cnt.ETHERNET_VLAN, 'Label type must be VLAN'
        vlan = int(label.labelValue())
        assert 1 <= vlan <= 4095, 'Invalid label value for vlan: %s' % label.labelValue()

        return Pica8OVSTarget(self.port_map[port], vlan)


    def createConnectionId(self, source_target, dest_target):
        return 'Pica8-' + str(random.randint(100000,999999))


    def canSwapLabel(self, label_type):
        return True


    def setupLink(self, connection_id, source_target, dest_target, bandwidth):

        def linkUp(_):
            log.msg('Link %s -> %s up' % (source_target, dest_target), system=LOG_SYSTEM)

        d = self.command_sender.setupLink(source_target, dest_target)
        d.addCallback(linkUp)
        return d


    def teardownLink(self, connection_id, source_target, dest_target, bandwidth):

        def linkDown(_):
            log.msg('Link %s -> %s down' % (source_target, dest_target), system=LOG_SYSTEM)

        d = self.command_sender.teardownLink(source_target, dest_target)
        d.addCallback(linkDown)
        return d



def Pica8OVSBackend(network_name, nrm_ports, parent_requester, cfg):

    name = 'Pica8OVS %s' % network_name
    nrm_map  = dict( [ (p.name, p) for p in nrm_ports ] ) # for the generic backend
    port_map = dict( [ (p.name, p.interface) for p in nrm_ports ] ) # for the nrm backend

    # extract config items
    host             = cfg[config.PICA8OVS_HOST]
    port             = cfg.get(config.PICA8OVS_PORT, 22)
    host_fingerprint = cfg[config.PICA8OVS_HOST_FINGERPRINT]
    user             = cfg[config.PICA8OVS_USER]
    ssh_public_key   = cfg[config.PICA8OVS_SSH_PUBLIC_KEY]
    ssh_private_key  = cfg[config.PICA8OVS_SSH_PRIVATE_KEY]
    db_ip            = cfg[config.PICA8OVS_DB_IP]

    cm = Pica8OVSConnectionManager(port_map, host, port, host_fingerprint, user, ssh_public_key, ssh_private_key, db_ip)
    return genericbackend.GenericBackend(network_name, nrm_map, cm, parent_requester, name)
