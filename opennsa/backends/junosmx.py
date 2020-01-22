"""
OpenNSA JUNOS MX backend
Currently only mpls, vlan and full port connections are supported

Author: Henrik Thostup Jensen < htj at nordu dot net >
Author: Tamas Varga <vargat(at)niif(dot)hu>

"""

import random

from twisted.python import log
from twisted.internet import defer

from opennsa import constants as cnt, config
from opennsa.backends.common import genericbackend, ssh



# parameterized commands
COMMAND_CONFIGURE           = 'edit private'
COMMAND_COMMIT              = 'commit'

COMMAND_SET_INTERFACES      = 'set interfaces %(port)s encapsulation ethernet-ccc' # port, source vlan, source vlan
COMMAND_SET_INTERFACES_CCC  = 'set interfaces %(port)s unit 0 family ccc'
COMMAND_SET_INTERFACES_MTU  = 'set interfaces %(port)s mtu 9000'

COMMAND_SET_FLEXIBLE_VLAN_T = 'set interfaces %(port)s flexible-vlan-tagging'
COMMAND_SET_INTERFACES_VLAN = 'set interfaces %(port)s encapsulation flexible-ethernet-services'
COMMAND_SET_VLAN_ENCAP      = 'set interfaces %(port)s unit %(vlan)s encapsulation vlan-ccc'
COMMAND_SET_VLAN_ID         = 'set interfaces %(port)s unit %(vlan)s vlan-id %(vlan)s'
COMMAND_SET_INPUT_VLAN_MAP  = 'set interfaces %(port)s unit %(vlan)s input-vlan-map pop'
COMMAND_SET_OUTPUT_VLAN_MAP = 'set interfaces %(port)s unit %(vlan)s output-vlan-map push'

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

LOG_SYSTEM = 'JUNOS'



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

            d = self.waitForLine('[edit]')
            self.write(COMMAND_CONFIGURE + LT)
            yield d

            log.msg('Entered configure mode', debug=True, system=LOG_SYSTEM)

            for cmd in commands:
                log.msg('CMD> %s' % cmd, system=LOG_SYSTEM)
                d = self.waitForLine('[edit]')
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

        except Exception as e:
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




class JUNOSCommandSender:

    def __init__(self, host, port, ssh_host_fingerprint, user, ssh_public_key_path, ssh_private_key_path,
            junos_routers,network_name):
        self.ssh_connection_creator = \
             ssh.SSHConnectionCreator(host, port, [ ssh_host_fingerprint ], user, ssh_public_key_path, ssh_private_key_path)

        self.ssh_connection = None # cached connection
        self.connection_lock = defer.DeferredLock()
        self.junos_routers = junos_routers
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

        cg = JUNOSCommandGenerator(connection_id,source_port,dest_port,self.junos_routers,self.network_name,bandwidth)
        commands = cg.generateActivateCommand() 
        return self._sendCommands(commands)


    def teardownLink(self, connection_id, source_port, dest_port, bandwidth):

        cg = JUNOSCommandGenerator(connection_id,source_port,dest_port,self.junos_routers,self.network_name,bandwidth)
        commands = cg.generateDeactivateCommand() 
        return self._sendCommands(commands)


class JUNOSTarget(object):

    def __init__(self, port, original_port,value=None):
        self.port = port
        self.value = value
        self.original_port = original_port
        # NEVER USE : in port name! 
    def __str__(self):
        if self.port.remote_network is None:
            if self.port.label is not None:
                return '<JUNOSTarget %s#%s=%s>' % (self.original_port,self.port.label.type_,self.value)
            else:
                return '<JUNOSTarget %s#>' % (self.original_port)
        else:
            if self.port.label is not None:
                return '<JUNOSTarget %s#%s=%s -> %s>' % (self.original_port,self.port.label.type_,self.value,self.port.remote_port)
            else:
                return '<JUNOSTarget %s# -> %s>' % (self.original_port,self.port.remote_port)



class JUNOSConnectionManager:

    def __init__(self, port_map, host, port, host_fingerprint, user, ssh_public_key, ssh_private_key,
            junos_routers,network_name):
        self.network_name = network_name
        self.port_map = port_map
        self.command_sender = JUNOSCommandSender(host, port, host_fingerprint, user, ssh_public_key, ssh_private_key,
                junos_routers,network_name)
        self.junos_routers = junos_routers
        self.supportedLabelPairs = {
                "mpls" : ['vlan','port'],
                "vlan" : ['port','mpls'],
                "port" : ['vlan','mpls']
        }


    def getResource(self, port, label):
        assert label is None or label.type_ in (cnt.MPLS, cnt.ETHERNET_VLAN), 'Label must be None or VLAN or MPLS'
        val = "" if label is None else str(label.labelValue())
        return port + ':' + val


    def getTarget(self, port, label):
        if label is None:
            return JUNOSTarget(self.port_map[port], port)
        else:
            return JUNOSTarget(self.port_map[port], port, label.labelValue())

    def createConnectionId(self, source_target, dest_target):
        return 'JUNOS-' + str(random.randint(100000,999999))


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


    def canConnect(self, source_port, dest_port, source_label, dest_label):
        src_label_type = 'port' if source_label is None else source_label.type_
        dst_label_type = 'port' if dest_label is None else dest_label.type_
        #by default, acccept same types
        if src_label_type == dst_label_type:
            return True
        elif src_label_type in self.supportedLabelPairs and dst_label_type in self.supportedLabelPairs[src_label_type]:
            return True
        else: 
            return False


def JUNOSMXBackend(network_name, nrm_ports , parent_requester, cfg):

    name = 'JUNOS %s' % network_name
    nrm_map  = dict( [ (p.name, p) for p in nrm_ports ] ) # for the generic backend
    port_map = dict( [ (p.name, p) for p in nrm_ports ] ) # for the nrm backend

    host             = cfg[config.JUNOS_HOST]
    port             = cfg.get(config.JUNOS_PORT, 22)
    host_fingerprint = cfg[config.JUNOS_HOST_FINGERPRINT]
    user             = cfg[config.JUNOS_USER]
    ssh_public_key   = cfg[config.JUNOS_SSH_PUBLIC_KEY]
    ssh_private_key  = cfg[config.JUNOS_SSH_PRIVATE_KEY]
    junos_routers_c    =  cfg[config.JUNOS_ROUTERS].split()
    junos_routers = dict()
    log.msg("Loaded JUNOS backend with routers:")
    for g in junos_routers_c:
        r,l = g.split(':',1)
        log.msg("Network: %s loopback: %s" % (r,l))
        junos_routers[r] = l
    cm = JUNOSConnectionManager(port_map, host, port, host_fingerprint, user, ssh_public_key, ssh_private_key,
            junos_routers,network_name)
    return genericbackend.GenericBackend(network_name, nrm_map, cm, parent_requester, name)


class JUNOSCommandGenerator(object):

    def __init__(self,connection_id,src_port,dest_port,junos_routers,network_name,bandwidth=None):
        self.connection_id = connection_id
        self.src_port = src_port
        self.dest_port = dest_port
        self.bandwidth = bandwidth
        self.junos_routers = junos_routers
        self.network_name = network_name
        log.msg('Initialised with params src %s dst %s bandwidth %s connectionid %s' %
                (src_port,dest_port,bandwidth,connection_id), debug=True, system=LOG_SYSTEM)


    def generateActivateCommand(self):
        commands = []

        source_port = self.src_port.port
        dest_port   = self.dest_port.port
        log.msg("Activate commands between %s and %s " %  (source_port,dest_port), debug=True, system=LOG_SYSTEM)

        # Local connection 
        if source_port.remote_network is None and dest_port.remote_network is None:
            commands = self._generateLocalConnectionActivate()
        elif source_port.remote_network is not None and dest_port.remote_network is not None:
            commands = self._generateTransitConnectionActivate()
        else: 
            commands = self._generateRemoteConnectionActivate()

        return commands


    def generateDeactivateCommand(self):
        commands = {}

        source_port = self.src_port.port
        dest_port   = self.dest_port.port
        log.msg("Deactivate commands between %s and %s " %  (source_port,dest_port), debug=True, system=LOG_SYSTEM)

        # Local connection 
        if source_port.remote_network is None and dest_port.remote_network is None:
            commands = self._generateLocalConnectionDeActivate()
        elif source_port.remote_network is not None and dest_port.remote_network is not None:
            commands = self._generateTransitConnectionDeactivate()
        else: 
            commands = self._generateRemoteConnectionDeactivate()

        return commands

    def _createSwitchName(self,connection_id):

        switch_name = 'NSI-%s' % (connection_id)

        return switch_name

    def _generateLocalConnectionActivate(self):
        commands = []
        switch_name = self._createSwitchName( self.connection_id )

        # For configuration reason, we're going to generate port things first, then the interface-switch commands
        for junos_port in self.src_port,self.dest_port:
            if junos_port.port.label is None:
                commands.append( COMMAND_SET_INTERFACES % { 'port':junos_port.port.interface} )
                commands.append( COMMAND_SET_INTERFACES_MTU % { 'port':junos_port.port.interface} )
                commands.append( COMMAND_SET_INTERFACES_CCC % { 'port':junos_port.port.interface} ) 
            elif junos_port.port.label.type_ == "vlan":
                commands.append( COMMAND_SET_FLEXIBLE_VLAN_T % {'port':junos_port.port.interface, 'vlan':junos_port.value} )
                commands.append( COMMAND_SET_INTERFACES_VLAN % {'port':junos_port.port.interface, 'vlan':junos_port.value} )
                commands.append( COMMAND_SET_VLAN_ENCAP % {'port':junos_port.port.interface, 'vlan':junos_port.value} )
                commands.append( COMMAND_SET_VLAN_ID % {'port':junos_port.port.interface, 'vlan':junos_port.value} )
                commands.append( COMMAND_SET_INPUT_VLAN_MAP % {'port':junos_port.port.interface, 'vlan':junos_port.value} )
                commands.append( COMMAND_SET_OUTPUT_VLAN_MAP % {'port':junos_port.port.interface, 'vlan':junos_port.value} )

        for junos_port in self.src_port,self.dest_port:
            commands.append( COMMAND_LOCAL_CONNECTIONS % { 'switch':switch_name, 
                                                       'interface':"%s" % junos_port.port.interface,
                                                       'subinterface': "%s" % junos_port.value if
                                                       junos_port.port.label is not None else '0' } )
        return commands


    def _generateLocalConnectionDeActivate(self):
        commands = []
        switch_name = self._createSwitchName( self.connection_id )

        for junos_port in self.src_port,self.dest_port:
            if junos_port.port.label is None:
                commands.append( COMMAND_DELETE_INTERFACES % { 'port':junos_port.port.interface } )
            elif junos_port.port.label.type_ == "vlan":
                commands.append( COMMAND_DELETE_INTERFACES_VL % { 'port':junos_port.port.interface, 'vlan' : "%s"
                    % junos_port.value})
        commands.append( COMMAND_DELETE_CONNECTIONS % { 'switch':switch_name } )

        return commands


    def _generateRemoteConnectionActivate(self):
        commands = []

        local_port = self.src_port if self.src_port.port.remote_network is None else self.dest_port
        remote_port = self.src_port if self.src_port.port.remote_network is not None else self.dest_port
        log.msg("%s" % local_port.original_port)
        log.msg("%s" % remote_port.original_port)

        if local_port.port.label is None:
            commands.append( COMMAND_SET_INTERFACES % { 'port':local_port.port.interface} )
            commands.append( COMMAND_SET_INTERFACES_MTU % { 'port':local_port.port.interface} )
            commands.append( COMMAND_SET_INTERFACES_CCC % { 'port':local_port.port.interface} ) 
        elif local_port.port.label.type_ == "vlan":
            commands.append( COMMAND_SET_FLEXIBLE_VLAN_T % {'port':local_port.port.interface, 'vlan':local_port.value} )
            commands.append( COMMAND_SET_INTERFACES_VLAN % {'port':local_port.port.interface, 'vlan':local_port.value} )
            commands.append( COMMAND_SET_VLAN_ENCAP % {'port':local_port.port.interface, 'vlan':local_port.value} )
            commands.append( COMMAND_SET_VLAN_ID % {'port':local_port.port.interface, 'vlan':local_port.value} )
            commands.append( COMMAND_SET_INPUT_VLAN_MAP % {'port':local_port.port.interface, 'vlan':local_port.value} )
            commands.append( COMMAND_SET_OUTPUT_VLAN_MAP % {'port':local_port.port.interface, 'vlan':local_port.value} )


        if remote_port.port.label is not None and remote_port.port.label.type_ == "mpls":
            remote_sw_ip = self._getRouterLoopback(remote_port.port.remote_network) 

            commands.append(COMMAND_REMOTE_LSP_OUT_TO % {
                'unique-id':"T-"+remote_port.port.remote_network[0:6]+"-F-"+self.network_name[0:6]+"-mpls"+str(remote_port.value),
                                                    'remote_ip':remote_sw_ip } )
            commands.append(COMMAND_REMOTE_LSP_OUT_NOCSPF % {
                'unique-id':"T-"+remote_port.port.remote_network[0:6]+"-F-"+self.network_name[0:6]+"-mpls"+str(remote_port.value),
                                                    'remote_ip':remote_sw_ip } )


            if local_port.port.label is None:
                commands.append(COMMAND_REMOTE_CONNECTIONS_INT % { 'connectionid' : self.connection_id,
                                                        'port' : local_port.port.interface
                                                        } )
            elif local_port.port.label.type_ == "vlan":
                 commands.append(COMMAND_REMOTE_CONNECTIONS_INT % { 'connectionid' : self.connection_id,
                                                        'port' : local_port.port.interface + "." + str(local_port.value)
                                                        } )

            commands.append(COMMAND_REMOTE_CONNECTIONS_TRANSMIT_LSP % { 'connectionid' : self.connection_id,
                                                        'unique-id':"T-"+remote_port.port.remote_network[0:6]+"-F-"+self.network_name[0:6]+"-mpls"+str(remote_port.value)
                                                        } )
            commands.append(COMMAND_REMOTE_CONNECTIONS_RECEIVE_LSP % { 'connectionid' : self.connection_id,
                                                        'unique-id':"T-"+self.network_name[0:6]+"-F-"+remote_port.port.remote_network[0:6]+"-mpls"+str(remote_port.value)
                                                        } )
        if remote_port.port.label is not None and remote_port.port.label.type_ == "vlan":
            switch_name = self._createSwitchName( self.connection_id )

            commands.append( COMMAND_SET_FLEXIBLE_VLAN_T % {'port':remote_port.port.interface, 'vlan':remote_port.value} )
            commands.append( COMMAND_SET_INTERFACES_VLAN % {'port':remote_port.port.interface, 'vlan':remote_port.value} )
            commands.append( COMMAND_SET_VLAN_ENCAP % {'port':remote_port.port.interface, 'vlan':remote_port.value} )
            commands.append( COMMAND_SET_VLAN_ID % {'port':remote_port.port.interface, 'vlan':remote_port.value} )
            commands.append( COMMAND_SET_INPUT_VLAN_MAP % {'port':remote_port.port.interface, 'vlan':remote_port.value} )
            commands.append( COMMAND_SET_OUTPUT_VLAN_MAP % {'port':remote_port.port.interface, 'vlan':remote_port.value} )

            for junos_port in local_port,remote_port:
                commands.append( COMMAND_LOCAL_CONNECTIONS % { 'switch':switch_name, 
                                                       'interface':"%s" % junos_port.port.interface,
                                                       'subinterface': "%s" % junos_port.value if
                                                       junos_port.port.label.type_ == "vlan" else '0' } )


        return commands


    def _generateRemoteConnectionDeactivate(self):
        commands = []

        local_port = self.src_port if self.src_port.port.remote_network is None else self.dest_port
        remote_port = self.src_port if self.src_port.port.remote_network is not None else self.dest_port

        if local_port.port.label is None:
            commands.append( COMMAND_DELETE_INTERFACES % { 'port':local_port.port.interface } )
        elif local_port.port.label.type_ == "vlan":
            commands.append( COMMAND_DELETE_INTERFACES_VL % { 'port':local_port.port.interface, 'vlan' : "%s"
                % local_port.value})

        if remote_port.port.label is not None and remote_port.port.label.type_ == "mpls":
            #remote_sw_ip = self._getRouterLoopback(remote_port.port.remote_network) 
            commands.append( COMMAND_DELETE_MPLS_LSP % {
                'unique-id' : "T-"+remote_port.port.remote_network[0:6]+"-F-"+self.network_name[0:6]+"-mpls"+str(remote_port.value)
                } )
            commands.append( COMMAND_DELETE_REMOTE_INT_SW % { 'connectionid' :
                    self.connection_id } )
        elif remote_port.port.label.type_ == "vlan":
            switch_name = self._createSwitchName( self.connection_id )
            commands.append( COMMAND_DELETE_INTERFACES_VL % { 'port':remote_port.port.interface, 'vlan' : "%s"
                % remote_port.value})
            commands.append( COMMAND_DELETE_CONNECTIONS % { 'switch':switch_name } )

        return commands

    def _generateTransitConnectionActivate(self):
        commands = []

        local_port = self.src_port
        remote_port = self.dest_port
        log.msg("%s" % local_port.original_port)
        log.msg("%s" % remote_port.original_port)

        if local_port.port.label is not None and local_port.port.label.type_ == "vlan":
            commands.append( COMMAND_SET_FLEXIBLE_VLAN_T % {'port':local_port.port.interface, 'vlan':local_port.value} )
            commands.append( COMMAND_SET_INTERFACES_VLAN % {'port':local_port.port.interface, 'vlan':local_port.value} )
            commands.append( COMMAND_SET_VLAN_ENCAP % {'port':local_port.port.interface, 'vlan':local_port.value} )
            commands.append( COMMAND_SET_VLAN_ID % {'port':local_port.port.interface, 'vlan':local_port.value} )
            commands.append( COMMAND_SET_INPUT_VLAN_MAP % {'port':local_port.port.interface, 'vlan':local_port.value} )
            commands.append( COMMAND_SET_OUTPUT_VLAN_MAP % {'port':local_port.port.interface, 'vlan':local_port.value} )

        if remote_port.port.label is not None and remote_port.port.label.type_ == "vlan":
            commands.append( COMMAND_SET_FLEXIBLE_VLAN_T % {'port':remote_port.port.interface, 'vlan':remote_port.value} )
            commands.append( COMMAND_SET_INTERFACES_VLAN % {'port':remote_port.port.interface, 'vlan':remote_port.value} )
            commands.append( COMMAND_SET_VLAN_ENCAP % {'port':remote_port.port.interface, 'vlan':remote_port.value} )
            commands.append( COMMAND_SET_VLAN_ID % {'port':remote_port.port.interface, 'vlan':remote_port.value} )
            commands.append( COMMAND_SET_INPUT_VLAN_MAP % {'port':remote_port.port.interface, 'vlan':remote_port.value} )
            commands.append( COMMAND_SET_OUTPUT_VLAN_MAP % {'port':remote_port.port.interface, 'vlan':remote_port.value} )

        if local_port.port.label is not None and local_port.port.label.type_ == "mpls":
            remote_sw_ip = self._getRouterLoopback(local_port.port.remote_network) 

            commands.append(COMMAND_REMOTE_LSP_OUT_TO % {
                'unique-id':"T-"+local_port.port.remote_network[0:6]+"-F-"+self.network_name[0:6]+"-mpls"+str(local_port.value),
                                                    'remote_ip':remote_sw_ip } )
            commands.append(COMMAND_REMOTE_LSP_OUT_NOCSPF % {
                'unique-id':"T-"+local_port.port.remote_network[0:6]+"-F-"+self.network_name[0:6]+"-mpls"+str(local_port.value),
                                                    'remote_ip':remote_sw_ip } )

            #Should not happen
            #if remote_port.port.label.type_ == "port":
            #    commands.append(COMMAND_REMOTE_CONNECTIONS_INT % { 'connectionid' : self.connection_id,
            #                                            'port' : remote_port.port.interface
            #                                            } )
            if remote_port.port.label is not None and remote_port.port.label.type_ == "vlan":
                 commands.append(COMMAND_REMOTE_CONNECTIONS_INT % { 'connectionid' : self.connection_id,
                                                        'port' : remote_port.port.interface + "." + str(remote_port.value)
                                                        } )

            commands.append(COMMAND_REMOTE_CONNECTIONS_TRANSMIT_LSP % { 'connectionid' : self.connection_id,
                                                        'unique-id':"T-"+local_port.port.remote_network[0:6]+"-F-"+self.network_name[0:6]+"-mpls"+str(local_port.value)
                                                        } )
            commands.append(COMMAND_REMOTE_CONNECTIONS_RECEIVE_LSP % { 'connectionid' : self.connection_id,
                                                        'unique-id':"T-"+self.network_name[0:6]+"-F-"+local_port.port.remote_network[0:6]+"-mpls"+str(local_port.value)
                                                        } )


        if remote_port.port.label is not None and remote_port.port.label.type_ == "mpls":
            remote_sw_ip = self._getRouterLoopback(remote_port.port.remote_network) 

            commands.append(COMMAND_REMOTE_LSP_OUT_TO % {
                'unique-id':"T-"+remote_port.port.remote_network[0:6]+"-F-"+self.network_name[0:6]+"-mpls"+str(remote_port.value),
                                                    'remote_ip':remote_sw_ip } )
            commands.append(COMMAND_REMOTE_LSP_OUT_NOCSPF % {
                'unique-id':"T-"+remote_port.port.remote_network[0:6]+"-F-"+self.network_name[0:6]+"-mpls"+str(remote_port.value),
                                                    'remote_ip':remote_sw_ip } )

            #Should not happen
            #if local_port.port.label.type_ == "port":
            #    commands.append(COMMAND_REMOTE_CONNECTIONS_INT % { 'connectionid' : self.connection_id,
            #                                            'port' : local_port.port.interface
            #                                            } )
            if local_port.port.label is not None and local_port.port.label.type_ == "vlan":
                 commands.append(COMMAND_REMOTE_CONNECTIONS_INT % { 'connectionid' : self.connection_id,
                                                        'port' : local_port.port.interface + "." + str(local_port.value)
                                                        } )

            commands.append(COMMAND_REMOTE_CONNECTIONS_TRANSMIT_LSP % { 'connectionid' : self.connection_id,
                                                        'unique-id':"T-"+remote_port.port.remote_network[0:6]+"-F-"+self.network_name[0:6]+"-mpls"+str(remote_port.value)
                                                        } )
            commands.append(COMMAND_REMOTE_CONNECTIONS_RECEIVE_LSP % { 'connectionid' : self.connection_id,
                                                        'unique-id':"T-"+self.network_name[0:6]+"-F-"+remote_port.port.remote_network[0:6]+"-mpls"+str(remote_port.value)
                                                        } )

        if remote_port.port.label is not None and remote_port.port.label.type_ == "vlan" and local_port.port.label is not None and local_port.port.label.type_ == "vlan":
            switch_name = self._createSwitchName( self.connection_id )

            for junos_port in local_port,remote_port:
                commands.append( COMMAND_LOCAL_CONNECTIONS % { 'switch':switch_name, 
                                                       'interface':"%s" % junos_port.port.interface,
                                                       'subinterface': "%s" % junos_port.value if
                                                       junos_port.port.label.type_ == "vlan" else '0' } )
        #TODO
        # we're missing 2 things here
        # mpls->mpls lsp stiching
        # port->something else crossconnect

        return commands


    def _generateTransitConnectionDeactivate(self):
        commands = []

        local_port = self.src_port 
        remote_port = self.dest_port

        if local_port.port.label is not None and local_port.port.label.type_ == "mpls":
            #remote_sw_ip = self._getRouterLoopback(local_port.port.remote_network) 
            commands.append( COMMAND_DELETE_MPLS_LSP % {
                'unique-id' : "T-"+local_port.port.remote_network[0:6]+"-F-"+self.network_name[0:6]+"-mpls"+str(local_port.value)
                } )
            #commands.append( COMMAND_DELETE_REMOTE_INT_SW % { 'connectionid' :
                    #self.connection_id } )
        if local_port.port.label is not None and local_port.port.label.type_ == "vlan":
            switch_name = self._createSwitchName( self.connection_id )
            commands.append( COMMAND_DELETE_INTERFACES_VL % { 'port':local_port.port.interface, 'vlan' : "%s"
                % local_port.value})
            #commands.append( COMMAND_DELETE_CONNECTIONS % { 'switch':switch_name } )

        if remote_port.port.label is not None and remote_port.port.label.type_ == "mpls":
            #remote_sw_ip = self._getRouterLoopback(remote_port.port.remote_network) 
            commands.append( COMMAND_DELETE_MPLS_LSP % {
                'unique-id' : "T-"+remote_port.port.remote_network[0:6]+"-F-"+self.network_name[0:6]+"-mpls"+str(remote_port.value)
                } )
            #commands.append( COMMAND_DELETE_REMOTE_INT_SW % { 'connectionid' :
                    #self.connection_id } )
        if remote_port.port.label is not None and remote_port.port.label.type_ == "vlan":
            switch_name = self._createSwitchName( self.connection_id )
            commands.append( COMMAND_DELETE_INTERFACES_VL % { 'port':remote_port.port.interface, 'vlan' : "%s"
                % remote_port.value})
            #commands.append( COMMAND_DELETE_CONNECTIONS % { 'switch':switch_name } )

        if local_port.port.label is not None and remote_port.port.label is not None:
            if remote_port.port.label.type_ == "mpls" or local_port.port.label.type_ == "mpls":
                            commands.append( COMMAND_DELETE_REMOTE_INT_SW % { 'connectionid' :
                        self.connection_id } )
            else:
                commands.append( COMMAND_DELETE_CONNECTIONS % { 'switch':switch_name } )


        return commands


    def _getRouterLoopback(self,network_name):

        if ":topology" in network_name:
            network_name = network_name.replace(":topology","")
        if network_name in self.junos_routers:
            return self.junos_routers[network_name]
        else:
           raise Exception("Can't find loopback IP address for network %s " % network_name)

