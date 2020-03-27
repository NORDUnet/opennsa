"""
OpenNSA JunosSpace backend
Currently only mpls, vlan and full port connections are supported
Author: Tamas Varga <vargat@niif.hu>

Description:

Basic Junosspace backend, which uses api calls based on the documentation.
In order to need to use this backend, configlets need to be added to the JunosSpace, and their respective number
needs to be configured in the config file.

The backend will shoot API calls over http to junosspace, using the predefined configlets, populating the variables
with the given data. The calls are carrying JSON as a payload. The format of the payload and available variables are
described in a different documentation alongside with the configlets.

The backend will not validate if the commands/request was successfully carried out by Junosspace. It'll post the the
given data, and if Junosspace returns with a success, it assumes, that junosspace will handle the rest, and the
command(s) is successfully delivered to the router.

Configuration:
[junosspace]
space_user=myuser           # username for junosspace
space_password=mypassword   # password for junosspace
space_api_url=http://1.1.1.1/myjunosspace # url for junosspace api
space_router=

TODO
- parse incoming job id and api link
- query for results
- implement remote part
- clean up the mess

"""

import json
import random
from base64 import b64encode
from pprint import pprint, pformat

from zope.interface import implements

from twisted.python import log
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.defer import setDebugging
from twisted.web.client import Agent,readBody
from twisted.web.http_headers import Headers
from twisted.internet.defer import succeed
from twisted.web.iweb import IBodyProducer
from twisted.internet.ssl import ClientContextFactory

from opennsa import constants as cnt, config
from opennsa.backends.common import genericbackend



setDebugging(True)

LOG_SYSTEM = 'JUNOSSPACE'

API_CALL_CONTENT_TYPE="application/vnd.net.juniper.space.configuration-management.apply-configlet+json;version=2;charset=UTF-8"
API_CALL_ACCEPT="application/vnd.net.juniper.space.job-management.task+json;version=1;q=.01"
LOCAL_ACTIVATE_CONFIGLET_ID     = "1578282"
REMOTE_ACTIVATE_CONFIGLET_ID    = "1578271"
LOCAL_DEACTIVATE_CONFIGLET_ID   = "1578251"
REMOTE_DEACTIVATE_CONFIGLET_ID  = "1578262"


class JUNOSSPACERouter(object):
    def __init__(self,router_name,router_id,router_ip):
        self.router_name = router_name
        self.router_id = router_id
        self.router_ip = router_ip

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "Router name {} deviceId {} loopback ip {}".format(self.router_name,self.router_id,self.router_ip)


class JUNOSSPACEPayloadProducer(object):
    implements(IBodyProducer)

    def __init__(self, json_payload):
        self.json_payload = json.dumps(json_payload['payload'])
        self.length = len(self.json_payload)

    def startProducing(self, consumer):
        consumer.write(self.json_payload)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class WebClientContextFactory(ClientContextFactory):
    def getContext(self, hostname, port):
        return ClientContextFactory.getContext(self)



class JUNOSSPACECommandSender:

    def __init__(self, space_user, space_password, space_api_url,  gts_routers,network_name):

        self.gts_routers = gts_routers
        self.network_name = network_name
        self.space_user = space_user
        self.space_password = space_password
        self.space_api_url = space_api_url
        log.msg("Space api url {} {}:{}".format(self.space_api_url,self.space_user,self.space_password))


    @defer.inlineCallbacks
    def _sendCommands(self, configlet_payload):

        log.msg('Sending junosspace command', debug=True, system=LOG_SYSTEM)
        authorization_string = b64encode(b"{}:{}".format(self.space_user,self.space_password))
        payload = JUNOSSPACEPayloadProducer(configlet_payload)
        api_configlet_url = "{}/configuration-management/cli-configlets/{}/apply-configlet".format(self.space_api_url,configlet_payload['configlet_id'])
        contextFactory = WebClientContextFactory()
        agent = Agent(reactor,contextFactory)
        req = agent.request(
            'POST',
            api_configlet_url,
            Headers({b"authorization": [b"Basic " + authorization_string],
                     b"Content-Type": [API_CALL_CONTENT_TYPE],
                     b"Accept": [API_CALL_ACCEPT]}),
                    payload)
        req.addCallbacks(self._cbRequest,self._cbError) 
        yield req


    def _cbRequest(self,response):
        print('Response version:', response.version)
        print('Response code:', response.code)
        print('Response phrase:', response.phrase)
        print('Response headers:')
        print(pformat(list(response.headers.getAllRawHeaders())))
        d = readBody(response)
        d.addCallback(self.printBody)
        return d

    def _cbError(self,failure):
        log.msg("{}".format(failure.value.reasons[0].printTraceback()),debug=True, system=LOG_SYSTEM)
        print(type(failure.value), failure) # catch error here

    def printBody(self,body):
        log.msg('Received body from junosspace {}'.format(body), debug=True, system=LOG_SYSTEM)


    def setupLink(self, connection_id, source_port, dest_port, bandwidth):
        cg = JUNOSSPACECommandGenerator(connection_id,source_port,dest_port,self.gts_routers,self.network_name,bandwidth)
        commands = cg.generateActivateCommand() 
        log.msg('Commands {}'.format(commands), debug=True, system=LOG_SYSTEM)
        return self._sendCommands(commands)


    def teardownLink(self, connection_id, source_port, dest_port, bandwidth):
        cg = JUNOSSPACECommandGenerator(connection_id,source_port,dest_port,self.gts_routers,self.network_name,bandwidth)
        commands = cg.generateDeactivateCommand() 
        log.msg('Commands {}'.format(commands), debug=True, system=LOG_SYSTEM)
        return self._sendCommands(commands)


class JUNOSSPACETarget(object):

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


class JUNOSSPACEConnectionManager:

    def __init__(self, port_map, space_user, space_password, space_api_url, space_routers,network_name):
        self.network_name = network_name
        self.port_map = port_map
        self.command_sender = JUNOSSPACECommandSender(space_user,space_password,space_api_url,space_routers,network_name)
        self.space_routers = space_routers
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
            return JUNOSSPACETarget(self.port_map[port], port)
        else:
            return JUNOSSPACETarget(self.port_map[port], port, label.labelValue())

    def createConnectionId(self, source_target, dest_target):
        return 'JUNOSSPACE-' + str(random.randint(100000,999999))


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


def JUNOSSPACEBackend(network_name, nrm_ports , parent_requester, cfg):

    name = 'JUNOSSPACE domain %s' % network_name
    nrm_map  = dict( [ (p.name, p) for p in nrm_ports ] ) # for the generic backend
    port_map = dict( [ (p.name, p) for p in nrm_ports ] ) # for the nrm backend

    space_user      = cfg[config.SPACE_USER]
    space_password  = cfg[config.SPACE_PASSWORD]
    space_api_url   = cfg[config.SPACE_API_URL]
    space_routers_config   = cfg[config.SPACE_ROUTERS].split()

    global LOCAL_ACTIVATE_CONFIGLET_ID
    global REMOTE_ACTIVATE_CONFIGLET_ID
    global LOCAL_DEACTIVATE_CONFIGLET_ID
    global REMOTE_DEACTIVATE_CONFIGLET_ID
    LOCAL_ACTIVATE_CONFIGLET_ID     = cfg[config.SPACE_CONFIGLET_ACTIVATE_LOCAL]
    REMOTE_ACTIVATE_CONFIGLET_ID    = cfg[config.SPACE_CONFIGLET_ACTIVATE_REMOTE]
    LOCAL_DEACTIVATE_CONFIGLET_ID   = cfg[config.SPACE_CONFIGLET_DEACTIVATE_LOCAL]
    REMOTE_DEACTIVATE_CONFIGLET_ID  = cfg[config.SPACE_CONFIGLET_DEACTIVATE_REMOTE]

    space_routers = dict()
    log.msg("Loaded JunosSpace backend with routers:")
    for g in space_routers_config:
        r,n,ip = g.split(':',2)
        junosspace_router = JUNOSSPACERouter(r,n,ip)
        log.msg("%s" % (junosspace_router))
        space_routers[r] = junosspace_router
    cm = JUNOSSPACEConnectionManager(port_map,space_user,space_password,space_api_url,space_routers,network_name)
    log.msg("Junosspace local activate configlet id {}".format(LOCAL_ACTIVATE_CONFIGLET_ID),debug=True,system=LOG_SYSTEM)
    log.msg("Junosspace remote activate configlet id {}".format(REMOTE_ACTIVATE_CONFIGLET_ID),debug=True,system=LOG_SYSTEM)
    log.msg("Junosspace local deactivate configlet id {}".format(LOCAL_DEACTIVATE_CONFIGLET_ID),debug=True,system=LOG_SYSTEM)
    log.msg("Junosspace remote deactivate configlet id {}".format(REMOTE_DEACTIVATE_CONFIGLET_ID),debug=True,system=LOG_SYSTEM)

    return genericbackend.GenericBackend(network_name, nrm_map, cm, parent_requester, name)


class JUNOSSPACECommandGenerator(object):

    def __init__(self,connection_id,src_port,dest_port,space_routers,network_name,bandwidth=None):
        self.connection_id = connection_id
        self.src_port = src_port
        self.dest_port = dest_port
        self.bandwidth = bandwidth
        self.space_routers = space_routers
        self.network_name = network_name
        log.msg('Initialised with params src %s dst %s bandwidth %s connectionid %s' %
                (src_port,dest_port,bandwidth,connection_id), debug=True, system=LOG_SYSTEM)


    def generateActivateCommand(self):

        source_port = self.src_port.port
        dest_port   = self.dest_port.port
        log.msg("%s %s " % (self.src_port,self.dest_port))
        log.msg("Activate commands between %s and %s " %  (source_port,dest_port), debug=True, system=LOG_SYSTEM)

        # Local connection 
        if source_port.remote_network is None and dest_port.remote_network is None:
            commands = self._generateLocalConnectionActivate()
        elif source_port.remote_network is not None and dest_port.remote_network is not None:
            commands = self._generateTransitConnectionActivate()
        else: 
            commands = self._generateRemoteConnectionActivate()
        pprint(commands,indent=2) 
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

        switch_name = 'GTS-local-%s' % (connection_id)
        return switch_name


    def _getDeviceId(self,network_name):
        if ":topology" in network_name:
            network_name = network_name.replace(":topology","")
        if network_name in self.space_routers:
            return self.space_routers[network_name].router_id
        else:
           raise Exception("Can't find deviceId for network %s " % network_name)


    def _getDeviceLoopbackIp(self,network_name):
        if ":topology" in network_name:
            network_name = network_name.replace(":topology","")
        if network_name in self.space_routers:
            return self.space_routers[network_name].router_ip
        else:
           raise Exception("Can't find router loopback ip for network %s " % network_name)

    def _createParamDict(self,paramname,paramvalue):
        paramd = {}
        paramd['parameter'] = paramname
        paramd['param-value'] = paramvalue
        return paramd

    def _generateLocalConnectionActivate(self):
        payload = {}
        commands = {}
        commands['configlet_id'] = LOCAL_ACTIVATE_CONFIGLET_ID
        commands['payload'] = {}
        commands['payload']['cli-configlet-mgmt'] = {}
        payload['deviceId'] = self._getDeviceId(self.network_name)
        payload['cli-configlet-param'] = []
        switch_name = self._createSwitchName( self.connection_id )
        src_label_type = 'port' if self.src_port.port.label is None else self.src_port.port.label.type_
        dst_label_type = 'port' if self.dest_port.port.label is None else self.dest_port.port.label.type_

        src_label_value = 0 if self.src_port.port.label is None else self.src_port.value
        dst_label_value = 0 if self.dest_port.port.label is None else self.dest_port.value

        # For configuration reason, we're going to generate port things first, then the interface-switch commands
        payload['cli-configlet-param'].append(self._createParamDict("LabelType1",src_label_type))
        payload['cli-configlet-param'].append(self._createParamDict("InterfaceName1",self.src_port.port.interface))
        payload['cli-configlet-param'].append(self._createParamDict("LabelValue1",src_label_value))
        payload['cli-configlet-param'].append(self._createParamDict("LabelType2",dst_label_type))
        payload['cli-configlet-param'].append(self._createParamDict("InterfaceName2",self.dest_port.port.interface))
        payload['cli-configlet-param'].append(self._createParamDict("LabelValue2",dst_label_value))
        payload['cli-configlet-param'].append(self._createParamDict("CircuitName",switch_name)) 

        commands['payload']['cli-configlet-mgmt'] = payload 
        return commands

    def _generateLocalConnectionDeActivate(self):
        payload = {}
        commands = {}
        commands['configlet_id'] = LOCAL_DEACTIVATE_CONFIGLET_ID
        commands['payload'] = {}
        commands['payload']['cli-configlet-mgmt'] = {}
        payload['deviceId'] = self._getDeviceId(self.network_name) 
        # should not pass param
        payload['cli-configlet-param'] = []
        switch_name = self._createSwitchName( self.connection_id )

        src_label_type = 'port' if self.src_port.port.label is None else self.src_port.port.label.type_
        dst_label_type = 'port' if self.dest_port.port.label is None else self.dest_port.port.label.type_

        src_label_value = 0 if self.src_port.port.label is None else self.src_port.value
        dst_label_value = 0 if self.dest_port.port.label is None else self.dest_port.value

        # For configuration reason, we're going to generate port things first, then the interface-switch commands
        payload['cli-configlet-param'].append(self._createParamDict("LabelType1",src_label_type))
        payload['cli-configlet-param'].append(self._createParamDict("InterfaceName1",self.src_port.port.interface))
        payload['cli-configlet-param'].append(self._createParamDict("LabelValue1",src_label_value))
        payload['cli-configlet-param'].append(self._createParamDict("LabelType2",dst_label_type))
        payload['cli-configlet-param'].append(self._createParamDict("InterfaceName2",self.dest_port.port.interface))
        payload['cli-configlet-param'].append(self._createParamDict("LabelValue2",dst_label_value))
        payload['cli-configlet-param'].append(self._createParamDict("CircuitName",switch_name))

        commands['payload']['cli-configlet-mgmt'] = payload 
        return commands

    def _generateRemoteConnectionActivate(self):

        local_port = self.src_port if self.src_port.port.remote_network is None else self.dest_port
        remote_port = self.src_port if self.src_port.port.remote_network is not None else self.dest_port
        if remote_port.port.label.type_ == "vlan":
            commands = self._generateLocalConnectionActivate()
        else:
            log.msg("%s" % local_port.original_port)
            log.msg("%s" % remote_port.original_port)

            payload = {}
            commands = {}
            commands['configlet_id'] = REMOTE_ACTIVATE_CONFIGLET_ID
            commands['payload'] = {}
            commands['payload']['cli-configlet-mgmt'] = {}
            payload['deviceId'] = self._getDeviceId(self.network_name) 
            # should not pass param
            payload['cli-configlet-param'] = []
            switch_name = self._createSwitchName( self.connection_id )

            local_label_type = 'port' if local_port.port.label is None else local_port.port.label.type_        
            local_label_value = 0 if local_port.port.label is None else local_port.value

            payload['cli-configlet-param'].append(self._createParamDict("LabelType",local_label_type))
            payload['cli-configlet-param'].append(self._createParamDict("InterfaceName",local_port.port.interface))
            payload['cli-configlet-param'].append(self._createParamDict("LabelValue",local_label_value))

            remote_sw_ip = self._getDeviceLoopbackIp(remote_port.port.remote_network)
            payload['cli-configlet-param'].append(self._createParamDict("TargetIP",remote_sw_ip))
            lsp_out_name = "T-{}-F-{}-mpls{}".format(remote_port.port.remote_network[0:6],self.network_name[0:6],str(remote_port.value))
            lsp_in_name = "T-{}-F-{}-mpls{}".format(self.network_name[0:6],remote_port.port.remote_network[0:6],str(remote_port.value))
            payload['cli-configlet-param'].append(self._createParamDict("LspNameOut",lsp_out_name))
            payload['cli-configlet-param'].append(self._createParamDict("LspNameIn",lsp_in_name))
            payload['cli-configlet-param'].append(self._createParamDict("CircuitName",switch_name))       

            commands['payload']['cli-configlet-mgmt'] = payload

        return commands


    def _generateRemoteConnectionDeactivate(self):
        local_port = self.src_port if self.src_port.port.remote_network is None else self.dest_port
        remote_port = self.src_port if self.src_port.port.remote_network is not None else self.dest_port
        if remote_port.port.label.type_ == "vlan":
            commands = self._generateLocalConnectionDeActivate()
        else:
            log.msg("%s" % local_port.original_port)
            log.msg("%s" % remote_port.original_port)

            payload = {}
            commands = {}
            commands['configlet_id'] = REMOTE_DEACTIVATE_CONFIGLET_ID
            commands['payload'] = {}
            commands['payload']['cli-configlet-mgmt'] = {}
            payload['deviceId'] = self._getDeviceId(self.network_name) 
            """ should not pass param """
            payload['cli-configlet-param'] = []
            switch_name = self._createSwitchName( self.connection_id )

            local_label_type = 'port' if local_port.port.label is None else local_port.port.label.type_        
            local_label_value = 0 if local_port.port.label is None else local_port.value

            payload['cli-configlet-param'].append(self._createParamDict("LabelType",local_label_type))
            payload['cli-configlet-param'].append(self._createParamDict("InterfaceName",local_port.port.interface))
            payload['cli-configlet-param'].append(self._createParamDict("LabelValue",local_label_value))

            remote_sw_ip = self._getDeviceLoopbackIp(remote_port.port.remote_network)
            payload['cli-configlet-param'].append(self._createParamDict("TargetIP",remote_sw_ip))
            lsp_out_name = "T-{}-F-{}-mpls{}".format(remote_port.port.remote_network[0:6],self.network_name[0:6],str(remote_port.value))
            lsp_in_name = "T-{}-F-{}-mpls{}".format(self.network_name[0:6],remote_port.port.remote_network[0:6],str(remote_port.value))
            payload['cli-configlet-param'].append(self._createParamDict("LspNameOut",lsp_out_name))
            payload['cli-configlet-param'].append(self._createParamDict("LspNameIn",lsp_in_name))
            payload['cli-configlet-param'].append(self._createParamDict("CircuitName",switch_name))       

            commands['payload']['cli-configlet-mgmt'] = payload
        return commands

    def _generateTransitConnectionActivate(self):

        if self.src_port.port.label is not None and self.dest_port.port.label is not None:

            if self.src_port.port.label.type_ == "vlan" and self.dest_port.port.label.type_ == "vlan":
                payload = {}
                commands = {}
                commands['configlet_id'] = LOCAL_ACTIVATE_CONFIGLET_ID
                commands['payload'] = {}
                commands['payload']['cli-configlet-mgmt'] = {}
                payload['deviceId'] = self._getDeviceId(self.network_name)
                payload['cli-configlet-param'] = []
                switch_name = self._createSwitchName( self.connection_id )

                # For configuration reason, we're going to generate port things first, then the interface-switch commands
                payload['cli-configlet-param'].append(self._createParamDict("LabelType1",self.src_port.port.label.type_))
                payload['cli-configlet-param'].append(self._createParamDict("InterfaceName1",self.src_port.port.interface))
                payload['cli-configlet-param'].append(self._createParamDict("LabelValue1",self.src_port.value))
                payload['cli-configlet-param'].append(self._createParamDict("LabelType2",self.dest_port.port.label.type_))
                payload['cli-configlet-param'].append(self._createParamDict("InterfaceName2",self.dest_port.port.interface))
                payload['cli-configlet-param'].append(self._createParamDict("LabelValue2",self.dest_port.value))
                payload['cli-configlet-param'].append(self._createParamDict("CircuitName",switch_name)) 

            elif self.src_port.port.label.type_ == "mpls" and self.dest_port.port.label.type_ == "mpls":
                raise Exception("MPLS lsp stitching not supported in this version")

            else:
                local_port = self.src_port if self.src_port.port.label.type_ == "vlan" else self.dest_port
                remote_port = self.src_port if self.src_port.port.label.type_ == "mpls" else self.dest_port

                if local_port.port.label.type_ == "vlan" and remote_port.port.label.type_ == "mpls":
                    log.msg("Transit vlan port %s" % local_port.original_port)
                    log.msg("Transit mpls port %s" % remote_port.original_port)

                    payload = {}
                    commands = {}
                    commands['configlet_id'] = REMOTE_ACTIVATE_CONFIGLET_ID
                    commands['payload'] = {}
                    commands['payload']['cli-configlet-mgmt'] = {}
                    payload['deviceId'] = self._getDeviceId(self.network_name) 
                    # should not pass param
                    payload['cli-configlet-param'] = []
                    switch_name = self._createSwitchName( self.connection_id )

                    payload['cli-configlet-param'].append(self._createParamDict("LabelType",local_port.port.label.type_))
                    payload['cli-configlet-param'].append(self._createParamDict("InterfaceName",local_port.port.interface))
                    payload['cli-configlet-param'].append(self._createParamDict("LabelValue",local_port.value))

                    remote_sw_ip = self._getDeviceLoopbackIp(remote_port.port.remote_network)
                    payload['cli-configlet-param'].append(self._createParamDict("TargetIP",remote_sw_ip))
                    lsp_out_name = "T-{}-F-{}-mpls{}".format(remote_port.port.remote_network[0:6],self.network_name[0:6],str(remote_port.value))
                    lsp_in_name = "T-{}-F-{}-mpls{}".format(self.network_name[0:6],remote_port.port.remote_network[0:6],str(remote_port.value))
                    payload['cli-configlet-param'].append(self._createParamDict("LspNameOut",lsp_out_name))
                    payload['cli-configlet-param'].append(self._createParamDict("LspNameIn",lsp_in_name))
                    payload['cli-configlet-param'].append(self._createParamDict("CircuitName",switch_name))
                else:
                    raise Exception("Bad combination of label types")
        else:
            raise Exception("Port based STPs not supported in transit nodes.")

        commands['payload']['cli-configlet-mgmt'] = payload
        return commands

    def _generateTransitConnectionDeactivate(self):

        if self.src_port.port.label is not None and self.dest_port.port.label is not None:

            if self.src_port.port.label.type_ == "vlan" and self.dest_port.port.label.type_ == "vlan":
                payload = {}
                commands = {}
                commands['configlet_id'] = LOCAL_DEACTIVATE_CONFIGLET_ID
                commands['payload'] = {}
                commands['payload']['cli-configlet-mgmt'] = {}
                payload['deviceId'] = self._getDeviceId(self.network_name) 
                # should not pass param
                payload['cli-configlet-param'] = []
                switch_name = self._createSwitchName( self.connection_id )

                # For configuration reason, we're going to generate port things first, then the interface-switch commands
                payload['cli-configlet-param'].append(self._createParamDict("LabelType1",self.src_port.port.label.type_))
                payload['cli-configlet-param'].append(self._createParamDict("InterfaceName1",self.src_port.port.interface))
                payload['cli-configlet-param'].append(self._createParamDict("LabelValue1",self.src_port.value))
                payload['cli-configlet-param'].append(self._createParamDict("LabelType2",self.dest_port.port.label.type_))
                payload['cli-configlet-param'].append(self._createParamDict("InterfaceName2",self.dest_port.port.interface))
                payload['cli-configlet-param'].append(self._createParamDict("LabelValue2",self.dest_port.value))
                payload['cli-configlet-param'].append(self._createParamDict("CircuitName",switch_name))

            elif self.src_port.port.label.type_ == "mpls" and self.dest_port.port.label.type_ == "mpls":
                raise Exception("MPLS lsp stitching not supported in this version")

            else:
                local_port = self.src_port if self.src_port.port.label.type_ == "vlan" else self.dest_port
                remote_port = self.src_port if self.src_port.port.label.type_ == "mpls" else self.dest_port

                if local_port.port.label.type_ == "vlan" and remote_port.port.label.type_ == "mpls":
                    log.msg("Transit vlan port %s" % local_port.original_port)
                    log.msg("Transit mpls port %s" % remote_port.original_port)

                    payload = {}
                    commands = {}
                    commands['configlet_id'] = REMOTE_DEACTIVATE_CONFIGLET_ID
                    commands['payload'] = {}
                    commands['payload']['cli-configlet-mgmt'] = {}
                    payload['deviceId'] = self._getDeviceId(self.network_name) 
                    """ should not pass param """
                    payload['cli-configlet-param'] = []
                    switch_name = self._createSwitchName( self.connection_id )

                    payload['cli-configlet-param'].append(self._createParamDict("LabelType",local_port.port.label.type_))
                    payload['cli-configlet-param'].append(self._createParamDict("InterfaceName",local_port.port.interface))
                    payload['cli-configlet-param'].append(self._createParamDict("LabelValue",local_port.value))

                    remote_sw_ip = self._getDeviceLoopbackIp(remote_port.port.remote_network)
                    payload['cli-configlet-param'].append(self._createParamDict("TargetIP",remote_sw_ip))
                    lsp_out_name = "T-{}-F-{}-mpls{}".format(remote_port.port.remote_network[0:6],self.network_name[0:6],str(remote_port.value))
                    lsp_in_name = "T-{}-F-{}-mpls{}".format(self.network_name[0:6],remote_port.port.remote_network[0:6],str(remote_port.value))
                    payload['cli-configlet-param'].append(self._createParamDict("LspNameOut",lsp_out_name))
                    payload['cli-configlet-param'].append(self._createParamDict("LspNameIn",lsp_in_name))
                    payload['cli-configlet-param'].append(self._createParamDict("CircuitName",switch_name))

                else:
                    raise Exception("Bad combination of label types")
        else:
            raise Exception("Port based STPs not supported in transit nodes.")

        commands['payload']['cli-configlet-mgmt'] = payload
        return commands



