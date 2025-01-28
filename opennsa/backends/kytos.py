"""
  Kytos-ng SDN Orchestrator Backend
  http://github.com/kytos-ng/mef_eline/

  Created by Italo Valcy/AmLight - italo@amlight.net

  Version 0.1 - Created to support AMPATH (May/2024)
  Version 0.2 - Updated to support Kytos-ng 2024.1 (Dez/2024)

"""

import random
import json
import traceback
from base64 import b64encode

from zope.interface import implementer

from twisted.python import log
from twisted.internet import reactor, defer
from twisted.internet.ssl import ClientContextFactory
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer

from opennsa import constants as cnt, config
from opennsa.backends.common import genericbackend


LOG_SYSTEM = "opennsa.Kytos"


# ********************************************************************************
# ************************* Twisted Mini Web Client ******************************
# ********************************************************************************


class WebClientContextFactory(ClientContextFactory):
    def getContext(self, hostname, port):
        return ClientContextFactory.getContext(self)


@implementer(IBodyProducer)
class KytosPayloadProducer(object):

    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()
        self.length = len(self.payload)

    def startProducing(self, consumer):
        consumer.write(self.payload)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


def http_query(conn, sub_path):
    """
    Mini Twisted Web Client - GET
    """
    full_url = conn.url + sub_path
    full_url = full_url.encode()
    log.msg("http_query: %r" % full_url, debug=True, system=LOG_SYSTEM)

    context_factory = WebClientContextFactory()
    agent = Agent(reactor, context_factory)
    d = agent.request(
        b"GET",
        full_url,
        headers=Headers(
            {
                "Content-Type": ["application/json"],
                "Authorization": ["Basic " + conn.auth.decode()],
            }
        ),
        bodyProducer=None,
    )
    d.addCallbacks(readBody, log.err)
    return d


def http_post(conn, sub_path, payload):
    """
    Mini Twisted Web Client - POST
    """
    full_url = conn.url + sub_path
    full_url = full_url.encode()
    log.msg(
        f"http_post: {full_url} payload={payload}",
        debug=True,
        system=LOG_SYSTEM,
    )

    context_factory = WebClientContextFactory()
    agent = Agent(reactor, context_factory)
    bodyProducer = KytosPayloadProducer(payload)
    d = agent.request(
        b"POST",
        full_url,
        headers=Headers(
            {
                "Content-Type": ["application/json"],
                "Authorization": ["Basic " + conn.auth.decode()],
            }
        ),
        bodyProducer=bodyProducer,
    )
    d.addCallbacks(readBody, log.err)
    return d


def http_delete(conn, sub_path):
    """
    Mini Twisted Web Client - DELETE
    """
    full_url = conn.url + sub_path
    full_url = full_url.encode()
    log.msg("http_delete: %r" % full_url, debug=True, system=LOG_SYSTEM)

    context_factory = WebClientContextFactory()
    agent = Agent(reactor, context_factory)
    d = agent.request(
        b"DELETE",
        full_url,
        headers=Headers(
            {
                "Content-Type": ["application/json"],
                "Authorization": ["Basic " + conn.auth.decode()],
            }
        ),
        bodyProducer=None,
    )
    d.addCallbacks(readBody, log.err)
    return d


# ********************************************************************************
# ****************************** Kytos Aux Functions ******************************
# ********************************************************************************


def kytos_get_circuit_id(circuits, switches, src_interface, dst_interface):
    s_sw, s_int, s_vlan = kytos_get_port_vlan(src_interface)
    d_sw, d_int, d_vlan = kytos_get_port_vlan(dst_interface)
    uni_a = {
        "interface_id": kytos_get_intf_id(switches, s_sw, s_int),
        "tag": {"tag_type": "vlan", "value": s_vlan},
    }
    uni_z = {
        "interface_id": kytos_get_intf_id(switches, d_sw, d_int),
        "tag": {"tag_type": "vlan", "value": d_vlan},
    }

    for circuit_id, circuit in circuits.items():
        if circuit["uni_a"] == uni_a and circuit["uni_z"] == uni_z:
            return circuit_id
        elif circuit["uni_z"] == uni_a and circuit["uni_a"] == uni_z:
            return circuit_id

    error_msg = f"Circuit not found for {src_interface} - {dst_interface}"
    log.msg(error_msg, system=LOG_SYSTEM)
    return 0


def kytos_process_result(result):
    try:
        result = json.loads(result)
        return result["circuit_id"]
    except Exception as exc:
        raise Exception(
            f"Unable to provision circuit ({result})." f"Check Kytos logs. Error: {exc}"
        )


def kytos_get_port_vlan(interface):
    (sw, int_vlan) = interface.split(":")
    (iface, vlan) = int_vlan.split("#")
    return sw, iface, int(vlan)


def kytos_get_intf_id(switches, sw_name, port_no):
    for swid, switch in switches.items():
        if all(
            [
                switch["metadata"].get("node_name") != sw_name,
                swid != sw_name,
                switch["name"] != sw_name,
            ]
        ):
            continue
        intf_id = f"{swid}:{port_no}"
        if intf_id not in switch["interfaces"]:
            raise Exception(
                f"Interface not found! Unknown port={port_no} in sw={sw_name}"
            )
        return intf_id
    raise Exception(f"Interface not found! Unknown sw={sw_name}")


@defer.inlineCallbacks
def kytos_provision_circuit(conn, s_intf_id, s_vlan, d_intf_id, d_vlan):
    payload = {
        "name": f"NSI-VLAN-{s_vlan}-{d_vlan}",
        "dynamic_backup_path": True,
        "uni_a": {
            "interface_id": s_intf_id,
            "tag": {"tag_type": "vlan", "value": s_vlan},
        },
        "uni_z": {
            "interface_id": d_intf_id,
            "tag": {"tag_type": "vlan", "value": d_vlan},
        },
    }
    p_query = "api/kytos/mef_eline/v2/evc/"
    retval = yield http_post(conn, p_query, payload)
    defer.returnValue(retval)


@defer.inlineCallbacks
def kytos_get_switches(conn):
    query = "api/kytos/topology/v3/switches/"
    retval = yield http_query(conn, query)
    defer.returnValue(retval)


@defer.inlineCallbacks
def kytos_get_circuits(conn):
    query = "api/kytos/mef_eline/v2/evc/"
    retval = yield http_query(conn, query)
    defer.returnValue(retval)


@defer.inlineCallbacks
def kytos_cancel_circuit(conn, circuit_id):
    cancel_query = f"api/kytos/mef_eline/v2/evc/{circuit_id}"
    retval = yield http_delete(conn, cancel_query)
    defer.returnValue(retval)


# ********************************************************************************
# ****************************** Kytos Setup Class *******************************
# ********************************************************************************


class UrlConnection(object):

    def __init__(self, url, auth):
        self.url = url
        self.auth = auth


class KytosSetup(object):

    def __init__(self, url, user, password):
        self.url = url
        self.username = user
        self.password = password
        self.circuit_id = None
        self.auth = b64encode(("%s:%s" % (self.username, self.password)).encode())
        self.conn = UrlConnection(self.url, self.auth)

    @defer.inlineCallbacks
    def kytos_provisioning(self, src_interface, dst_interface):
        log.msg("Provisioning Kytos circuit... ", system=LOG_SYSTEM)
        try:
            log.msg("01 - Getting Kytos switches", debug=True, system=LOG_SYSTEM)
            result = yield kytos_get_switches(self.conn)
            kytos_switches = json.loads(result)["switches"]

            log.msg(
                "02 - Getting source switch, interface and VLAN from src_interface",
                debug=True,
                system=LOG_SYSTEM,
            )
            s_sw, s_int, s_vlan = kytos_get_port_vlan(src_interface)

            log.msg(
                "03 - Convert source interface into Kytos interface_id",
                debug=True,
                system=LOG_SYSTEM,
            )
            s_intf_id = kytos_get_intf_id(kytos_switches, s_sw, s_int)

            log.msg(
                "04 - Get destination switch, interface and VLAN from dst_interface",
                debug=True,
                system=LOG_SYSTEM,
            )
            d_sw, d_int, d_vlan = kytos_get_port_vlan(dst_interface)

            log.msg(
                "05 - Convert destination interface into Kytos interface_id",
                debug=True,
                system=LOG_SYSTEM,
            )
            d_intf_id = kytos_get_intf_id(kytos_switches, d_sw, d_int)

        except Exception as exc:
            err = traceback.format_exc().replace("\n", ", ")
            log.msg(
                f"Error preparing to create circuit: {exc} - {err}", system=LOG_SYSTEM
            )
            raise exc

        for i in range(0, 3):
            log.msg(
                "06 - Provisioning circuit... (try %d)" % i,
                debug=True,
                system=LOG_SYSTEM,
            )
            try:
                result = yield kytos_provision_circuit(
                    self.conn, s_intf_id, s_vlan, d_intf_id, d_vlan
                )
                self.circuit_id = kytos_process_result(result)
            except Exception as exc:
                err = traceback.format_exc().replace("\n", ", ")
                log.msg(
                    f"Error creating circuit (try {i}): {exc} - {err}",
                    system=LOG_SYSTEM,
                )
            else:
                log.msg(
                    f"Kytos EVC {self.circuit_id} created successfully",
                    system=LOG_SYSTEM,
                )
                break
        else:
            raise Exception("Failed to create circuit after many tries")

    @defer.inlineCallbacks
    def kytos_circuit_removal(self, src_interface, dst_interface):
        log.msg(
            f"Removing Kytos circuit src={src_interface} dst={dst_interface}",
            system=LOG_SYSTEM,
        )
        try:
            log.msg("01 - Getting Kytos switches", debug=True, system=LOG_SYSTEM)
            result = yield kytos_get_switches(self.conn)
            kytos_switches = json.loads(result)["switches"]

            log.msg("02 - Getting list of circuits", debug=True, system=LOG_SYSTEM)
            result = yield kytos_get_circuits(self.conn)
            kytos_circuits = json.loads(result)

            log.msg("03 - Getting Circuit ID", debug=True, system=LOG_SYSTEM)
            circuit_id = kytos_get_circuit_id(
                kytos_circuits, kytos_switches, src_interface, dst_interface
            )

            if not circuit_id:
                log.msg("Kytos circuit not found!", debug=True, system=LOG_SYSTEM)
            else:
                log.msg("04 - Cancelling Circuit ID", debug=True, system=LOG_SYSTEM)
                result = yield kytos_cancel_circuit(self.conn, circuit_id)
                result = json.loads(result)

                if f"Circuit {circuit_id} removed" in result["response"]:
                    log.msg(f"Kytos circuit {circuit_id} removed", system=LOG_SYSTEM)
                else:
                    log.msg(f"Failed to remove Kytos circuit: {result}")

        except Exception as exc:
            err = traceback.format_exc().replace("\n", ", ")
            log.msg(f"Error removing circuit: {exc} - {err}", system=LOG_SYSTEM)
            raise exc

    def setupLink(self, source_target, dest_target):
        return self.kytos_provisioning(source_target, dest_target)

    def tearDownLink(self, source_target, dest_target):
        return self.kytos_circuit_removal(source_target, dest_target)


# ******************************************************************************
# ************************** Kytos Connection Manager **************************
# ******************************************************************************


class KytosConnectionManager:

    def __init__(self, log_system, port_map, url, user, password):
        self.log_system = log_system
        self.port_map = port_map
        self.kytos_conn = KytosSetup(url, user, password)
        self.circuit_id = None

    def getResource(self, port, label):
        log.msg(
            "Kytos: getResource, port = %s and label = %s and Vlan = %s"
            % (port, label, label.labelValue()),
            system=self.log_system,
        )

        assert (
            label is not None or label.type_ == cnt.ETHERNET_VLAN
        ), "Label type must be VLAN"
        # resource is port + vlan (router / virtual switching)
        label_value = "" if label is None else label.labelValue()
        return port + ":" + label_value

    def getTarget(self, port, label):
        log.msg(
            "Kytos: getTarget, port = %s and label = %s" % (port, label),
            system=self.log_system,
        )

        assert (
            label is not None and label.type_ == cnt.ETHERNET_VLAN
        ), "Label type must be VLAN"
        vlan = int(label.labelValue())
        assert 1 <= vlan <= 4094, (
            "Invalid label value for vlan: %s" % label.labelValue()
        )
        return self.port_map[port] + "#" + str(vlan)

    def createConnectionId(self, source_target, dest_target):
        return "Kytos-" + str(random.randint(100000, 999999))

    def canSwapLabel(self, label_type):
        return True

    def setupLink(self, connection_id, source_target, dest_target, bandwidth):
        def logSetupLink(pt, source_target, dest_target):
            log.msg(
                "Link %s -> %s up" % (source_target, dest_target),
                system=self.log_system,
            )
            return pt

        log.msg(
            f"Kytos: setupLink {source_target} {dest_target}",
            debug=True,
            system=self.log_system,
        )
        d = self.kytos_conn.setupLink(source_target, dest_target)
        d.addCallback(logSetupLink, source_target, dest_target)

        return d

    def teardownLink(self, connection_id, source_target, dest_target, bandwidth):
        def logTearDownLink(pt, source_target, dest_target):
            log.msg(
                "Link %s -> %s down" % (source_target, dest_target),
                system=self.log_system,
            )
            return pt

        log.msg(
            f"Kytos: tearDownLink {source_target} {dest_target}",
            debug=True,
            system=self.log_system,
        )
        d = self.kytos_conn.tearDownLink(source_target, dest_target)
        d.addCallback(logTearDownLink, source_target, dest_target)

        return d


# ********************************************************************************
# ************************** Kytos Backend Definition ****************************
# ********************************************************************************


def KytosBackend(network_name, nrm_ports, parent_requester, cfg):
    """
    Kytos Backend definition
    """
    log.msg("Kytos: KytosBackend", debug=True, system=LOG_SYSTEM)
    name = "Kytos NRM %s" % network_name
    # for the generic backend
    nrm_map = dict([(p.name, p) for p in nrm_ports])
    # for the nrm backend
    port_map = dict([(p.name, p.interface) for p in nrm_ports])

    # Configuration items
    kytos_url = cfg[config.KYTOS_URL]
    kytos_user = cfg[config.KYTOS_USER]
    kytos_pass = cfg[config.KYTOS_PASSWORD]

    cm = KytosConnectionManager(name, port_map, kytos_url, kytos_user, kytos_pass)
    return genericbackend.GenericBackend(
        network_name, nrm_map, cm, parent_requester, name, minimum_duration=1
    )
