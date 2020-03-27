"""
The built-in logging in twisted.web.http.HTTPFactory.log is before Twisted got
a logging framework, and hence integrates poorly with the other logging. This
is a replacement log method that makes it look nice.

Copyright NORDUnet: 2014

Author: Henrik Thostrup Jensen <htj@nordu.net>
"""

from twisted.python import log


LOG_SYSTEM = 'HTTP'


def logRequest(request):

    length      = request.sentLength or '-'
    user_agent  = request.getHeader('user-agent') or '-'

    log.msg('{} - {} {} {} {} {} {}'.format(
        request.getClientIP(),
        request.method.decode(),
        request.uri.decode(),
        request.clientproto.decode(),
        request.code,
        length,
        user_agent),
        system=LOG_SYSTEM
    )

