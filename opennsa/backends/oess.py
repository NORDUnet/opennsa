"""
  OESS Backend

  Created by Jeronimo Bezerra/AmLight - jab@amlight.net
  Enhanced by AJ Ragusa GlobalNOC - aragusa@grnoc.iu.edu
  Comments by Henrik Jensen - htj@nordu.net

  Version 0.1 - Created to support AMPATH (Jul/2015)
  Version 0.2 - Enhanced to support Async calls, replacing urllib2 (Dec/2016)

"""

import random
import json
from base64 import b64encode

from twisted.python import log
from twisted.internet import reactor, defer
from twisted.internet.ssl import ClientContextFactory
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers

from opennsa.backends.common import genericbackend
from opennsa import constants as cnt, config


LOG_SYSTEM = 'opennsa.OESS'


# ********************************************************************************
# ************************* Twisted Mini Web Client ******************************
# ********************************************************************************


class WebClientContextFactory(ClientContextFactory):
    def getContext(self, hostname, port):
        return ClientContextFactory.getContext(self)


def http_query(conn, sub_path):
    """
    Mini Twisted Web Client
    """
    full_url = conn.url + sub_path
    full_url = full_url.encode('latin-1')
    log.msg("http_query: %r" % full_url, debug=True, system=LOG_SYSTEM)

    context_factory = WebClientContextFactory()
    agent = Agent(reactor, context_factory)
    d = agent.request('GET', full_url,
                      headers=Headers(
                       {'Content-Type': ['application/x-www-form-urlencoded'],
                        'Authorization': ['Basic ' + conn.auth]
                        }),
                      bodyProducer=None)
    d.addCallbacks(readBody, log.err)
    return d


# ********************************************************************************
# ****************************** OESS Aux Functions ******************************
# ********************************************************************************


def oess_get_circuit_id(circuits, src_interface, dst_interface):
    s_sw, s_int, s_vlan = oess_get_port_vlan(src_interface)
    d_sw, d_int, d_vlan = oess_get_port_vlan(dst_interface)
    circuits = json.loads(circuits)
    for circuit in circuits["results"]:
        if circuit["endpoints"][0]["node"] == s_sw:
            if circuit["endpoints"][1]["node"] == d_sw:
                if circuit["endpoints"][0]["interface"] == s_int:
                    if circuit["endpoints"][1]["interface"] == d_int:
                        return circuit["circuit_id"]

        elif circuit["endpoints"][0]["node"] == d_sw:
            if circuit["endpoints"][1]["node"] == s_sw:
                if circuit["endpoints"][0]["interface"] == d_int:
                    if circuit["endpoints"][1]["interface"] == s_int:
                        return circuit["circuit_id"]

    error_msg = "Circuit not found for %s - %s" % (src_interface, dst_interface)
    log.msg(error_msg, system=LOG_SYSTEM)
    return 0


def oess_process_result(result):
    try:
        result = json.loads(result)
        if result["results"]["success"] == 1:
            return result["results"]["circuit_id"]
    except:
            raise Exception("Unable to provision circuit. Check OESS logs")


def oess_process_path(result):
    try:
        result = json.loads(result)
    except Exception as err:
        raise Exception(err)
    path = []
    for link in result["results"]:
            path.append(link['link'])
    return path


def oess_confirm_vlan_availability(result, vlan):
    try:
        result = json.loads(result)
    except Exception as err:
        raise Exception(err)
    if result["results"][0]["available"] == 1:
        return True
    raise Exception("Vlan %s not available" % vlan)


def oess_validate_ports(switch_interfaces, intf):
    try:
        switch_interfaces = json.loads(switch_interfaces)
    except Exception as err:
        raise Exception(err)
    for switch_interface in switch_interfaces["results"]:
        if switch_interface["name"] == intf:
            return True
    raise Exception("Incorrect Interface - interface %s" % intf)


def oess_get_workgroup_id(wg_ids, group):
    try:
        wg_ids = json.loads(wg_ids)
    except Exception as err:
        raise Exception(err)
    for wg_id in wg_ids["results"]:
        if wg_id["name"] == group:
            return wg_id["workgroup_id"]
    raise Exception("Incorrect Group %s" % group)


def oess_get_port_vlan(interface):
    (sw, int_vlan) = interface.split(':')
    (iface, vlan) = int_vlan.split('#')
    return sw, iface, vlan


@defer.inlineCallbacks
def oess_provision_circuit(conn, wg_id, s_sw, s_int, s_vlan,
                           d_sw, d_int, d_vlan, primary_path, backup_path):
    p_query = 'services/provisioning.cgi?'
    p_query += 'action=provision_circuit&workgroup_id=%s' % wg_id
    p_query += '&node=%s&interface=%s&tag=%s' % (s_sw, s_int, s_vlan)
    p_query += '&node=%s&interface=%s&tag=%s' % (d_sw, d_int, d_vlan)

    for link in primary_path:
        p_query += "&link=" + link

    for link in backup_path:
        p_query += "&backup_link=" + link

    p_query += '&provision_time=-1&remove_time=-1'
    p_query += '&description=NSI-VLAN-%s-%s' % (s_vlan, d_vlan)
    retval = yield http_query(conn, p_query)
    defer.returnValue(retval)


@defer.inlineCallbacks
def oess_get_path(conn, s_sw, d_sw, primary=None):
    query = "services/data.cgi?action="
    query += "get_shortest_path&node=%s&node=%s" % (s_sw, d_sw)
    if primary is not None:
        for link in primary:
            query += "&link=%s" % link
    retval = yield http_query(conn, query)
    defer.returnValue(retval)


@defer.inlineCallbacks
def oess_query_vlan_availability(conn, sw, intf, vlan):
    query = "services/data.cgi?action=is_vlan_tag_available"
    query += "&node=%s&interface=%s&vlan=%s" % (sw, intf, vlan)
    retval = yield http_query(conn, query)
    defer.returnValue(retval)


@defer.inlineCallbacks
def oess_get_switch_ports(conn, node):
    query = 'services/data.cgi?action=get_node_interfaces&node=%s' % node
    retval = yield http_query(conn, query)
    defer.returnValue(retval)


@defer.inlineCallbacks
def oess_get_workgroups(conn):
    query = 'services/data.cgi?action=get_workgroups'
    retval = yield http_query(conn, query)
    defer.returnValue(retval)


@defer.inlineCallbacks
def oess_get_circuits(conn, workgroup_id):
    query = 'services/data.cgi?'
    query += 'action=get_existing_circuits&workgroup_id=%s' % workgroup_id
    retval = yield http_query(conn, query)
    defer.returnValue(retval)


@defer.inlineCallbacks
def oess_cancel_circuit(conn, circuit_id, wg_id):
    cancel_query = "services/provisioning.cgi?action="
    cancel_query += "remove_circuit&remove_time=-1"
    cancel_query += "&workgroup_id=%s&circuit_id=%s" % (wg_id, circuit_id)

    retval = yield http_query(conn, cancel_query)
    defer.returnValue(retval)


# ********************************************************************************
# ****************************** OESS Setup Class ********************************
# ********************************************************************************


class UrlConnection(object):

    def __init__(self, url, auth):
        self.url = url
        self.auth = auth


class OessSetup(object):

    def __init__(self, url, user, password, workgroup):
        self.url = url
        self.username = user
        self.password = password
        self.workgroup = workgroup
        self.workgroup_id = None
        self.circuit_id = None
        self.auth = b64encode(b"%s:%s" % (self.username, self.password))
        self.conn = UrlConnection(self.url, self.auth)

    @defer.inlineCallbacks
    def oess_provisioning(self, src_interface, dst_interface):
        log.msg("Provisioning OESS circuit... ", system=LOG_SYSTEM)
        try:
            log.msg("01 - Getting All OESS Workgroup' Workgroup_IDs",
                    debug=True, system=LOG_SYSTEM)
            wg_ids = yield oess_get_workgroups(self.conn)

            log.msg("02 - Getting our Group's ID",
                    debug = True, system=LOG_SYSTEM)
            self.workgroup_id = oess_get_workgroup_id(wg_ids, self.workgroup)

            log.msg("03 - Getting source switch, interface and VLAN from src_interface",
                    debug=True, system=LOG_SYSTEM)
            s_sw, s_int, s_vlan = oess_get_port_vlan(src_interface)

            log.msg("04 - Querying for all interfaces of the source switch",
                    debug=True, system=LOG_SYSTEM)
            s_switch_interfaces = yield oess_get_switch_ports(self.conn, s_sw)

            log.msg("05 - Validating switch_interfaces with interface provided",
                    debug=True, system=LOG_SYSTEM)
            oess_validate_ports(s_switch_interfaces, s_int)

            log.msg("06 - Verifying if source VLAN is available",
                    debug=True, system=LOG_SYSTEM)
            is_available = yield oess_query_vlan_availability(self.conn, s_sw, s_int, s_vlan)
            oess_confirm_vlan_availability(is_available, s_vlan)

            log.msg("07 - Get destination switch, interface and VLAN from dst_interface",
                    debug=True, system=LOG_SYSTEM)
            d_sw, d_int, d_vlan = oess_get_port_vlan(dst_interface)

            log.msg("08 - Querying for all interfaces of the destination switch",
                    debug=True, system=LOG_SYSTEM)
            d_switch_interfaces = yield oess_get_switch_ports(self.conn, d_sw)

            log.msg("09 - Validating switch_interfaces with interface provided",
                    debug=True, system=LOG_SYSTEM)
            oess_validate_ports(d_switch_interfaces, d_int)

            log.msg("10 - Verifying if destination VLAN is available",
                    debug=True, system=LOG_SYSTEM)
            is_available = yield oess_query_vlan_availability(self.conn, d_sw, d_int, d_vlan)
            oess_confirm_vlan_availability(is_available, d_vlan)

            log.msg("11 - Querying for primary path",
                    debug=True, system=LOG_SYSTEM)
            p_path = yield oess_get_path(self.conn, s_sw, d_sw)
            primary = oess_process_path(p_path)

            log.msg("12 - Querying for backup path",
                    debug=True, system=LOG_SYSTEM)
            b_path = yield oess_get_path(self.conn, s_sw, d_sw, primary)
            backup = oess_process_path(b_path)

            log.msg("13 - Provisioning circuit...",
                    debug=True, system=LOG_SYSTEM)
            result = yield oess_provision_circuit(self.conn, self.workgroup_id,
                                                  s_sw, s_int, s_vlan,
                                                  d_sw, d_int, d_vlan,
                                                  primary, backup)
            self.circuit_id = oess_process_result(result)

            log.msg("Success!! OESS circuit %s created" % self.circuit_id,
                    system=LOG_SYSTEM)

        except Exception as err:
            log.msg("Error creating circuit: %s" % err, system=LOG_SYSTEM)
            raise err


    @defer.inlineCallbacks
    def oess_circuit_removal(self, src_interface, dst_interface):
        log.msg("Removing OESS circuit", system=LOG_SYSTEM)
        try:
            log.msg("01 - Getting list of circuits", debug=True, system=LOG_SYSTEM)
            circuits = yield oess_get_circuits(self.conn, self.workgroup_id)

            log.msg("02 - Getting Circuit ID", debug=True, system=LOG_SYSTEM)
            circuit_id = oess_get_circuit_id(circuits, src_interface, dst_interface)

            if not circuit_id:
                log.msg("OESS circuit not found!", debug=True, system=LOG_SYSTEM)
            else:
                log.msg("03 - Cancelling Circuit ID", debug=True, system=LOG_SYSTEM)
                result = yield oess_cancel_circuit(self.conn, str(circuit_id),
                                                   self.workgroup_id)
                try:
                    try:
                        result = json.loads(result)
                    except Exception as err:
                        raise err

                    if result["results"][0]["success"] == 1:
                        log.msg("OESS circuit %s removed'" % circuit_id, system=LOG_SYSTEM)
                except:
                    raise Exception("Problem removing circuit %s. Check OESS's logs"
                                    % circuit_id)

        except Exception as err:
            log.msg("Error creating circuit: %s" % err, system=LOG_SYSTEM)
            raise err

    def setupLink(self, source_target, dest_target):
        return self.oess_provisioning(source_target, dest_target)

    def tearDownLink(self, source_target, dest_target):
        return self.oess_circuit_removal(source_target, dest_target)


# ******************************************************************************
# ************************** OESS Connection Manager ***************************
# ******************************************************************************


class OESSConnectionManager:

    def __init__(self, log_system, port_map, url, user, password, workgroup):
        self.log_system = log_system
        self.port_map = port_map
        self.oess_conn = OessSetup(url, user, password, workgroup)
        self.circuit_id = None

    def getResource(self, port, label):
        log.msg('OESS: getResource, port = %s and label = %s and Vlan = %s' %
                (port, label, label.labelValue()), system=self.log_system)

        assert label is not None or label.type_ == cnt.ETHERNET_VLAN, 'Label type must be VLAN'
        # resource is port + vlan (router / virtual switching)
        label_value = '' if label is None else label.labelValue()
        return port + ':' + label_value

    def getTarget(self, port, label):
        log.msg('OESS: getTarget, port = %s and label = %s' % (port, label),
                system=self.log_system)

        assert label is not None and label.type_ == cnt.ETHERNET_VLAN, 'Label type must be VLAN'
        vlan = int(label.labelValue())
        assert 1 <= vlan <= 4094, 'Invalid label value for vlan: %s' % label.labelValue()
        return self.port_map[port] + '#' + str(vlan)

    def createConnectionId(self, source_target, dest_target):
        return 'OESS-' + str(random.randint(100000, 999999))

    def canSwapLabel(self, label_type):
        return True

    def setupLink(self, connection_id, source_target, dest_target, bandwidth):
        log.msg('OESS: setupLink', debug=True, system=self.log_system)
        self.oess_conn.setupLink(source_target, dest_target)
        log.msg('Link %s -> %s up' % (source_target, dest_target),
                system=self.log_system)
        return defer.succeed(None)

    def teardownLink(self, connection_id, source_target, dest_target, bandwidth):
        # Debug
        log.msg('OESS: teardownLink', system=self.log_system)
        self.oess_conn.tearDownLink(source_target, dest_target)
        log.msg('Link %s -> %s down' % (source_target, dest_target),
                system=self.log_system)
        return defer.succeed(None)


# ********************************************************************************
# ************************** OESS Backend Definition *****************************
# ********************************************************************************


def OESSBackend(network_name, nrm_ports, parent_requester, cfg):
    """
    OESS Backend definition
    """
    log.msg('OESS: OESSBackend', debug=True, system=LOG_SYSTEM)
    name = 'OESS NRM %s' % network_name
    # for the generic backend
    nrm_map = dict([(p.name, p) for p in nrm_ports])
    # for the nrm backend
    port_map = dict([(p.name, p.interface) for p in nrm_ports])

    # Configuration items
    oess_url = cfg[config.OESS_URL]
    oess_user = cfg[config.OESS_USER]
    oess_pass = cfg[config.OESS_PASSWORD]
    oess_workgroup = cfg[config.OESS_WORKGROUP]

    cm = OESSConnectionManager(name, port_map, oess_url, oess_user,
                               oess_pass, oess_workgroup)
    return genericbackend.GenericBackend(network_name, nrm_map, cm,
                                         parent_requester, name,
                                         minimum_duration=1)
