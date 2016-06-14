"""
HTTP request authorization

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2013-2016)
"""

from twisted.python import log

from opennsa.shared.requestinfo import RequestInfo

LOG_SYSTEM='protocol.authZ'


def checkAuthz(request, allowed_hosts):
    # returns allowed, msg, request_info
    # not the best api in the world, but it works
    # msg is None if allowed, otherwise it contains the reson to relay to the client

    allowed = False
    msg = None
    request_info = RequestInfo()

    if allowed_hosts is None:
        allowed = True # no allowed hosts -> all are allowed access (further authz may be performed in other layers)

        # fill in request info as we might need in port authZ
        if request.isSecure():
            # log certificate subject
            cert = request.transport.getPeerCertificate()
            if cert:
                log.msg('Certificate subject %s' % cert.get_subject(), system=LOG_SYSTEM)
                host_dn = cert.get_subject().get_components()[-1][1]
                request_info = RequestInfo(str(cert.get_subject()), host_dn)


    else: # we have an allowed host list
        if not request.isSecure():
            log.msg('Rejecting request, not secure (no ssl/tls)', system=LOG_SYSTEM)
            msg = 'Insecure requests not allowed for this resource'
            return allowed, msg, request_info

        cert = request.transport.getPeerCertificate()
        if not cert:
            log.msg('Rejecting request, no client certificate provided', system=LOG_SYSTEM)
            msg = 'Requests without client certificate not allowed'
            return allowed, msg, request_info

        cert_subject = cert.get_subject()
        log.msg('Certificate subject %s' % cert.get_subject(), system=LOG_SYSTEM)
        host_dn = cert.get_subject().get_components()[-1][1]
        log.msg('Host DN: %s' % host_dn, system=LOG_SYSTEM)

        request_info = RequestInfo(str(cert_subject), host_dn)

        if host_dn in allowed_hosts:
            allowed = True
        else:
            log.msg('Rejecting request, certificate host dn does not match allowed hosts', system=LOG_SYSTEM)
            msg = 'Requests not authorized for this resource'

    return allowed, msg, request_info

