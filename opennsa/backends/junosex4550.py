"""
OpenNSA GTS backend, using Junos on EX4550 switches
Currently only vlan connections are supported
Authors: 
Original GTS backend: Tamas Varga <vargat@niif.hu>
Modified for EX4550 Michal Hazlinksy <hazlinsky@cesnet.cz>
"""
import random

from twisted.python import log
from twisted.internet import defer

from opennsa import constants as cnt, config
from opennsa.backends.common import genericbackend, ssh

# parameterized commands
COMMAND_CONFIGURE           = 'configure'
COMMAND_COMMIT              = 'commit'

COMMAND_SET_INTERFACES      = 'set interfaces %(port)s encapsulation ethernet-ccc' # port, source vlan, source vlan
COMMAND_SET_INTERFACES_CCC  = 'set interfaces %(port)s unit 0 family ccc'
COMMAND_SET_INTERFACES_MTU  = 'set interfaces %(port)s mtu 9000'

COMMAND_SET_INTERFACE_VLN_T = 'set interfaces %(port)s vlan-tagging'
COMMAND_SET_INTERFACE_ENC_V = 'set interfaces %(port)s encapsulation vlan-ccc'
COMMAND_SET_VLAN_ENCAP      = 'set interfaces %(port)s unit %(vlan)s encapsulation vlan-ccc'
COMMAND_SET_VLAN_ID         = 'set interfaces %(port)s unit %(vlan)s vlan-id %(vlan)s'
COMMAND_SET_SWAP_PUSH_POP   = 'set interfaces %(port)s unit %(vlan)s swap-by-poppush'

COMMAND_DELETE_INTERFACES   = 'delete interfaces %(port)s' # port / vlan
COMMAND_DELETE_INTERFACES_VL= 'delete interfaces %(port)s.%(vlan)s'
COMMAND_DELETE_CONNECTIONS  = 'delete protocols connections interface-switch %(switch)s' # switch

COMMAND_DELETE_MPLS_LSP     = 'delete protocols mpls label-switched-path %(unique-id)s'
COMMAND_DELETE_REMOTE_INT_SW= 'delete protocols connections remote-interface-switch %(connectionid)s'

COMMAND_LOCAL_CONNECTIONS   = 'set protocols connections interface-switch %(switch)s interface %(interface)s.%(subinterface)s'

COMMAND_REMOTE_LSP_OUT_TO   = 'set protocols mpls label-switched-path %(unique-id)s to %(remote_ip)s'
COMMAND_REMOTE_LSP_OUT_NOCSPF = 'set protocols mpls label-switched-path %(unique-id)s no-cspf'

COMMAND_REMOTE_CONNECTIONS_INT = 'set protocols connections remote-interface-switch %(connectionid)s interface %(port)s'
COMMAND_REMOTE_CONNECTIONS_TRANSMIT_LSP = 'set protocols connections remote-interface-switch %(connectionid)s transmit-lsp %(unique-id)s'
COMMAND_REMOTE_CONNECTIONS_RECEIVE_LSP  = 'set protocols connections remote-interface-switch %(connectionid)s receive-lsp %(unique-id)s'

LOG_SYSTEM = 'EX4550'

class SSHChannel(ssh.SSHChannel):

    name = 'session'

    def __init__(self, conn):
        ssh.SSHChannel.__init__(self, conn=conn)

        self.line = ''

        self.wait_defer = None
        self.wait_line  = None


    @defer.inlineCallbacks
    def sendCommands(self, commands):
        LT = '\r' # line termination

        try:
            yield self.conn.sendRequest(self, 'shell', '', wantReply=1)

            d = self.waitForLine('{master:0}[edit]')
            self.write(COMMAND_CONFIGURE + LT)
            yield d

            log.msg('Entered configure mode', debug=True, system=LOG_SYSTEM)

            for cmd in commands:
                log.msg('CMD> %s' % cmd, system=LOG_SYSTEM)
                d = self.waitForLine('{master:0}[edit]')
                self.write(cmd + LT)
                yield d

            # commit commands, check for 'commit complete' as success
            # not quite sure how to handle failure here

            ## test stuff
            #d = self.waitForLine('[edit]')
            #self.write('commit check' + LT)

            d = self.waitForLine('commit complete')
            self.write(COMMAND_COMMIT + LT)
            yield d

        except Exception, e:
            log.msg('Error sending commands: %s' % str(e))
            raise e

        log.msg('Commands successfully committed', debug=True, system=LOG_SYSTEM)
        self.sendEOF()
        self.closeIt()


    def waitForLine(self, line):
        self.wait_line = line
        self.wait_defer = defer.Deferred()
        return self.wait_defer


    def matchLine(self, line):
        if self.wait_line and self.wait_defer:
            if self.wait_line == line.strip():
                d = self.wait_defer
                self.wait_line  = None
                self.wait_defer = None
                d.callback(self)
            else:
                pass


    def dataReceived(self, data):
        if len(data) == 0:
            pass
        else:
            self.line += data
            if '\n' in data:
                lines = [ line.strip() for line in self.line.split('\n') if line.strip() ]
                self.line = ''
                for l in lines:
                    self.matchLine(l)




class JunosEx4550CommandSender:

    def __init__(self, host, port, ssh_host_fingerprint, user, ssh_public_key_path, ssh_private_key_path,
            network_name):
        self.ssh_connection_creator = \
             ssh.SSHConnectionCreator(host, port, [ ssh_host_fingerprint ], user, ssh_public_key_path, ssh_private_key_path)

        self.ssh_connection = None # cached connection
        self.connection_lock = defer.DeferredLock()
        self.network_name = network_name

    def _getSSHChannel(self):

        def setSSHConnectionCache(ssh_connection):
            log.msg('SSH Connection created and cached', system=LOG_SYSTEM)
            self.ssh_connection = ssh_connection
            return ssh_connection

        def gotSSHConnection(ssh_connection):
            channel = SSHChannel(conn = ssh_connection)
            ssh_connection.openChannel(channel)
            return channel.channel_open

        if self.ssh_connection:
            log.msg('Reusing SSH connection', debug=True, system=LOG_SYSTEM)
            return gotSSHConnection(self.ssh_connection)
        else:
            # since creating a new connection should be uncommon, we log it
            # this makes it possible to see if something fucks up and creates connections continuously
            log.msg('Creating new SSH connection', system=LOG_SYSTEM)
            d = self.ssh_connection_creator.getSSHConnection()
            d.addCallback(setSSHConnectionCache)
            d.addCallback(gotSSHConnection)
            return d


    @defer.inlineCallbacks
    def _sendCommands(self, commands):

        channel = yield self._getSSHChannel()
        log.msg('Acquiring ssh session lock', debug=True, system=LOG_SYSTEM)
        yield self.connection_lock.acquire()
        log.msg('Got ssh session lock', debug=True, system=LOG_SYSTEM)

        try:
            yield channel.sendCommands(commands)
        finally:
            log.msg('Releasing ssh session lock', debug=True, system=LOG_SYSTEM)
            self.connection_lock.release()
            log.msg('Released ssh session lock', debug=True, system=LOG_SYSTEM)


    def setupLink(self, connection_id, source_port, dest_port, bandwidth):

        cg = JunosEx4550CommandGenerator(connection_id,source_port,dest_port,self.network_name,bandwidth)
        commands = cg.generateActivateCommand() 
        return self._sendCommands(commands)


    def teardownLink(self, connection_id, source_port, dest_port, bandwidth):

        cg = JunosEx4550CommandGenerator(connection_id,source_port,dest_port,self.network_name,bandwidth)
        commands = cg.generateDeactivateCommand() 
        return self._sendCommands(commands)


class JunosEx4550Target(object):

    def __init__(self, port, original_port,value=None):
        self.port = port
        self.value = value
        self.original_port = original_port
        # NEVER USE : in port name! 
    def __str__(self):
        if self.port.remote_network is None:
            return '<JuniperEX4550Target %s#%s=%s>' % (self.original_port,self.port.label.type_,self.value)
        else:
            return '<JuniperEX4550Target %s#%s=%s -> %s>' % (self.original_port,self.port.label.type_,self.value,self.port.remote_port,)



class JunosEx4550ConnectionManager:

    def __init__(self, port_map, host, port, host_fingerprint, user, ssh_public_key, ssh_private_key,
            network_name):
        self.network_name = network_name
        self.port_map = port_map
        self.command_sender = JunosEx4550CommandSender(host, port, host_fingerprint, user, ssh_public_key, ssh_private_key,
                network_name)
        
        #IMHO - Can be removed since EX4550 supports vlan to vlan connections only
        #self.supportedLabelPairs = {
        #        "mpls" : ['vlan','port'],
        #        "vlan" : ['port','mpls'],
        #        "port" : ['vlan','mpls']
        #        
        #        }


    def getResource(self, port, label_type, label_value):
        assert label_type in (None, cnt.ETHERNET_VLAN), 'Label must be None,or VLAN'
        return port + "-" + str(label_type) + "=" + str(label_value)

    def getTarget(self, port, label_type, label_value):
        return JunosEx4550Target(self.port_map[port], port,label_value)

    def createConnectionId(self, source_target, dest_target):
        return 'JuniperEx4550-' + str(random.randint(100000,999999))


    def canSwapLabel(self, label_type):
        return True


    def setupLink(self, connection_id, source_target, dest_target, bandwidth):
        def linkUp(_):
            log.msg('Link %s -> %s up' % (source_target, dest_target), system=LOG_SYSTEM)
        d = self.command_sender.setupLink(connection_id,source_target, dest_target,bandwidth)
        d.addCallback(linkUp)
        return d


    def teardownLink(self, connection_id, source_target, dest_target, bandwidth):
        def linkDown(_):
            log.msg('Link %s -> %s down' % (source_target, dest_target), system=LOG_SYSTEM)
        d = self.command_sender.teardownLink(connection_id,source_target, dest_target, bandwidth)
        d.addCallback(linkDown)
        return d

    
    def canConnectLabels(self,src_label_type,dst_label_type):
        log.msg("Check label pair %s %s" % (src_label_type,dst_label_type),system=LOG_SYSTEM)
        #by default, acccept same types
        if src_label_type == dst_label_type:
            return True
        #if src_label_type in self.supportedLabelPairs and dst_label_type in self.supportedLabelPairs[src_label_type]:
        #    return True
        # commented out because of removal the pairs definition above

def JunosEx4550Backend(network_name, nrm_ports , parent_requester, cfg):

    name = 'JunosEx4550 %s' % network_name
    nrm_map  = dict( [ (p.name, p) for p in nrm_ports ] ) # for the generic backend
    port_map = dict( [ (p.name, p) for p in nrm_ports ] ) # for the nrm backend

    host             = cfg[config.JunosEx4550_HOST]
    port             = cfg.get(config.JunosEx4550_PORT, 22)
    host_fingerprint = cfg[config.JunosEx4550_HOST_FINGERPRINT]
    user             = cfg[config.JunosEx4550_USER]
    ssh_public_key   = cfg[config.JunosEx4550_SSH_PUBLIC_KEY]
    ssh_private_key  = cfg[config.JunosEx4550_SSH_PRIVATE_KEY]
    
    cm = JunosEx4550ConnectionManager(port_map, host, port, host_fingerprint, user, ssh_public_key, ssh_private_key,
            network_name)
    return genericbackend.GenericBackend(network_name, nrm_map, cm, parent_requester, name)


class JunosEx4550CommandGenerator(object):
     
    def __init__(self,connection_id,src_port,dest_port,network_name,bandwidth=None):
        self.connection_id = connection_id
        self.src_port = src_port
        self.dest_port = dest_port
        self.bandwidth = bandwidth
        self.network_name = network_name
        log.msg('Initialised with params src %s dst %s bandwidth %s connectionid %s' %
                (src_port,dest_port,bandwidth,connection_id), debug=True, system=LOG_SYSTEM)


    def generateActivateCommand(self):
        commands = []

        source_port = self.src_port.port
        dest_port   = self.dest_port.port
        log.msg("%s %s " % (source_port,dest_port))
        log.msg("Activate commands between %s:%s:%s and %s:%s:%s " % 
                (source_port.remote_network, source_port.interface, source_port.label.type_,
                    dest_port.remote_network, dest_port.interface, dest_port.label.type_), debug=True,
                system=LOG_SYSTEM)

        # Local connection 
        if source_port.remote_network is None and dest_port.remote_network is None:
            commands = self._generateLocalConnectionActivate()
        elif source_port.remote_network is not None and dest_port.remote_network is not None:
            commands = self._generateLocalConnectionActivate()
            log.msg('Transit connection-HERE SHOULD BE COMMANDS FOR TRANSIT', system=LOG_SYSTEM)
        else: 
            #commands = self._generateRemoteConnectionActivate()  All cases are the same tODO: remove IFs competely here 
            commands = self._generateLocalConnectionActivate()
        return commands


    def generateDeactivateCommand(self):
        commands = {}

        source_port = self.src_port.port
        dest_port   = self.dest_port.port
        log.msg("Deactivate commands between %s:%s#%s=%s and %s:%s#%s=%s " % 
                (source_port.remote_network, source_port.interface, source_port.label.type_,self.src_port.value,
                    dest_port.remote_network, dest_port.interface, dest_port.label.type_,self.dest_port.value), debug=True,
                system=LOG_SYSTEM)

        # Local connection 
        if source_port.remote_network is None and dest_port.remote_network is None:
            commands = self._generateLocalConnectionDeActivate()
        elif source_port.remote_network is not None and dest_port.remote_network is not None:
            #commands = ["Transit connection"]
            commands = self._generateLocalConnectionDeActivate()
        else: 
            #commands = self._generateRemoteConnectionDeactivate()   DTTO as activate
            commands = self._generateLocalConnectionDeActivate()

 


        return commands

    def _createSwitchName(self,connection_id):

        switch_name = 'OpenNSA-local-%s' % (connection_id)
        
        return switch_name

    def _generateLocalConnectionActivate(self):
        commands = []
        switch_name = self._createSwitchName( self.connection_id )

        """ For configuration reason, we're going to generate port things first, then the interface-switch commands"""
        for gts_port in self.src_port,self.dest_port:
            #if gts_port.port.label is not None and gts_port.port.label.type_ == "port":
            #    commands.append( COMMAND_SET_INTERFACES % { 'port':gts_port.port.interface} )
            #    commands.append( COMMAND_SET_INTERFACES_MTU % { 'port':gts_port.port.interface} )
            #    commands.append( COMMAND_SET_INTERFACES_CCC % { 'port':gts_port.port.interface} )
            # tODO remove this as ports are not supported 
            if gts_port.port.label is not None and gts_port.port.label.type_ == "vlan":
                commands.append( COMMAND_SET_INTERFACE_VLN_T % {'port':gts_port.port.interface, 'vlan':gts_port.value} )
                commands.append( COMMAND_SET_INTERFACES_MTU % { 'port':gts_port.port.interface} )
                commands.append( COMMAND_SET_INTERFACE_ENC_V % {'port':gts_port.port.interface, 'vlan':gts_port.value} )
                commands.append( COMMAND_SET_VLAN_ENCAP % {'port':gts_port.port.interface, 'vlan':gts_port.value} )
                commands.append( COMMAND_SET_VLAN_ID % {'port':gts_port.port.interface, 'vlan':gts_port.value} )
                commands.append( COMMAND_SET_SWAP_PUSH_POP % {'port':gts_port.port.interface, 'vlan':gts_port.value} )

        
        for gts_port in self.src_port,self.dest_port:
            commands.append( COMMAND_LOCAL_CONNECTIONS % { 'switch':switch_name, 
                                                       'interface':"%s" % gts_port.port.interface,
                                                       'subinterface': "%s" % gts_port.value if
                                                       gts_port.port.label.type_ == "vlan" else '0' } )
        
        return commands

    def _generateLocalConnectionDeActivate(self):
        commands = []
        switch_name = self._createSwitchName( self.connection_id )

        for gts_port in self.src_port,self.dest_port:
            #if gts_port.port.label.type_ == "port":
             #   commands.append( COMMAND_DELETE_INTERFACES % { 'port':gts_port.port.interface } )
            if gts_port.port.label is not None and gts_port.port.label.type_ == "vlan":
                commands.append( COMMAND_DELETE_INTERFACES_VL % { 'port':gts_port.port.interface, 'vlan' : "%s"
                    % gts_port.value})
        commands.append( COMMAND_DELETE_CONNECTIONS % { 'switch':switch_name } )

        return commands

#    def _generateRemoteConnectionActivate(self):
#        commands = []
#        
#        local_port = self.src_port if self.src_port.port.remote_network is None else self.dest_port
#        remote_port = self.src_port if self.src_port.port.remote_network is not None else self.dest_port
#        log.msg("%s" % local_port.original_port)
#        log.msg("%s" % remote_port.original_port)
#        
#        if local_port.port.label.type_ == "port":
#            commands.append( COMMAND_SET_INTERFACES % { 'port':local_port.port.interface} )
#            commands.append( COMMAND_SET_INTERFACES_MTU % { 'port':local_port.port.interface} )
#            commands.append( COMMAND_SET_INTERFACES_CCC % { 'port':local_port.port.interface} ) 
#        if local_port.port.label.type_ == "vlan":
#            commands.append( COMMAND_SET_INTERFACE_VLN_T % {'port':local_port.port.interface, 'vlan':local_port.value} )
#            commands.append( COMMAND_SET_INTERFACE_ENC_V % {'port':local_port.port.interface, 'vlan':local_port.value} )
#            commands.append( COMMAND_SET_VLAN_ENCAP % {'port':local_port.port.interface, 'vlan':local_port.value} )
#            commands.append( COMMAND_SET_VLAN_ID % {'port':local_port.port.interface, 'vlan':local_port.value} )
#            commands.append( COMMAND_SET_SWAP_PUSH_POP % {'port':local_port.port.interface, 'vlan':local_port.value} )
#       
#        if remote_port.port.label.type_ == "mpls":
#            remote_sw_ip = self._getRouterLoopback(remote_port.port.remote_network) 
#            
#            commands.append(COMMAND_REMOTE_LSP_OUT_TO % {
#                'unique-id':"T-"+remote_port.port.remote_network+"-F-"+self.network_name+"-mpls"+str(remote_port.value),
#                                                    'remote_ip':remote_sw_ip } )
#            commands.append(COMMAND_REMOTE_LSP_OUT_NOCSPF % {
#                'unique-id':"T-"+remote_port.port.remote_network+"-F-"+self.network_name+"-mpls"+str(remote_port.value),
#                                                    'remote_ip':remote_sw_ip } )
#
#
#            if local_port.port.label.type_ == "port":
#                commands.append(COMMAND_REMOTE_CONNECTIONS_INT % { 'connectionid' : self.connection_id,
#                                                        'port' : local_port.port.interface
#                                                        } )
#            if local_port.port.label.type_ == "vlan":
#                 commands.append(COMMAND_REMOTE_CONNECTIONS_INT % { 'connectionid' : self.connection_id,
#                                                        'port' : local_port.port.interface + "." + str(local_port.value)
#                                                        } )
#                   
#            commands.append(COMMAND_REMOTE_CONNECTIONS_TRANSMIT_LSP % { 'connectionid' : self.connection_id,
#                                                        'unique-id':"T-"+remote_port.port.remote_network+"-F-"+self.network_name+"-mpls"+str(remote_port.value)
#                                                        } )
#            commands.append(COMMAND_REMOTE_CONNECTIONS_RECEIVE_LSP % { 'connectionid' : self.connection_id,
#                                                        'unique-id':"T-"+self.network_name+"-F-"+remote_port.port.remote_network+"-mpls"+str(remote_port.value)
#                                                        } )
#        if remote_port.port.label.type_ == "vlan":
#            switch_name = self._createSwitchName( self.connection_id )
#            
#            commands.append( COMMAND_SET_INTERFACE_VLN_T % {'port':remote_port.port.interface, 'vlan':remote_port.value} )
#            commands.append( COMMAND_SET_INTERFACE_ENC_V % {'port':remote_port.port.interface, 'vlan':remote_port.value} )
#            commands.append( COMMAND_SET_VLAN_ENCAP % {'port':remote_port.port.interface, 'vlan':remote_port.value} )
#            commands.append( COMMAND_SET_VLAN_ID % {'port':remote_port.port.interface, 'vlan':remote_port.value} )
#            commands.append( COMMAND_SET_SWAP_PUSH_POP % {'port':remote_port.port.interface, 'vlan':remote_port.value} )
#            
#            for gts_port in local_port,remote_port:
#                commands.append( COMMAND_LOCAL_CONNECTIONS % { 'switch':switch_name, 
#                                                       'interface':"%s" % gts_port.port.interface,
#                                                       'subinterface': "%s" % gts_port.value if
#                                                       gts_port.port.label.type_ == "vlan" else '0' } )
#
#
#        return commands
#
#
#    def _generateRemoteConnectionDeactivate(self):
#        commands = []
#
#        local_port = self.src_port if self.src_port.port.remote_network is None else self.dest_port
#        remote_port = self.src_port if self.src_port.port.remote_network is not None else self.dest_port
#        
#        if local_port.port.label.type_ == "port":
#            commands.append( COMMAND_DELETE_INTERFACES % { 'port':local_port.port.interface } )
#        if local_port.port.label.type_ == "vlan":
#            commands.append( COMMAND_DELETE_INTERFACES_VL % { 'port':local_port.port.interface, 'vlan' : "%s"
#                % local_port.value})
#
#        if remote_port.port.label.type_ == "mpls":
#            remote_sw_ip = self._getRouterLoopback(remote_port.port.remote_network) 
#            commands.append( COMMAND_DELETE_MPLS_LSP % {
#                'unique-id' : "T-"+remote_port.port.remote_network+"-F-"+self.network_name+"-mpls"+str(remote_port.value)
#                } )
#            commands.append( COMMAND_DELETE_REMOTE_INT_SW % { 'connectionid' :
#                    self.connection_id } )
#        if remote_port.port.label.type_ == "vlan":
#            switch_name = self._createSwitchName( self.connection_id )
#            commands.append( COMMAND_DELETE_INTERFACES_VL % { 'port':remote_port.port.interface, 'vlan' : "%s"
#                % remote_port.value})
#            commands.append( COMMAND_DELETE_CONNECTIONS % { 'switch':switch_name } )
#
#        return commands

    #def _getRouterLoopback(self,network_name):
#
#        if ":topology" in network_name:
#            network_name = network_name.replace(":topology","")
#        if network_name in self.gts_routers:
#            return self.gts_routers[network_name]
#        else:
#           raise Exception("Can't find loopback IP address for network %s " % network_name)
