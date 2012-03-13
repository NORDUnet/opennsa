"""
HTTP Resource for displaying connection in OpenNSA.

Currently rather simple.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012)
"""

from twisted.web import resource, server


HTML_HEADER = """<!DOCTYPE html>
<html>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
        <title>%(title)s</title>
    </head>
    <body>
"""

HTML_FOOTER = """   </body>
</html>
"""


class ConnectionListResource(resource.Resource):

    def __init__(self, nsi_service):
        self.nsi_service = nsi_service


    def render_GET(self, request):

        ib = 4 * ' '

        body =''
        body += 2*ib + '<h3>OpenNSA Connections</h3>\n'
        body += 2*ib + '<p>\n'

        for nsa, conns in sorted(self.nsi_service.connections.items()):

            body += 2*ib + '<div>%s</div>\n' % nsa
            body += 2*ib + '<p>\n'

            for conn_id, conn in conns.items():
                sp = conn.service_parameters
                body += 2*ib + '<div>%s : %s | %s - %s</div>\n' % (conn_id, conn.state(), sp.start_time, sp.end_time)
                body += 2*ib + '<p>\n'

            body += 2*ib + '<p> &nbsp; <p>\n'
            break # so else block don't get triggered

        else:

            body += '<div>No connections defined</div>\n'

        body = str(body)

        request.write(HTML_HEADER % {'title': 'OpenNSA Connections'} )
        request.write(body)
        request.write(HTML_FOOTER)
        request.finish()
        return server.NOT_DONE_YET

