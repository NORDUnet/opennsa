"""
HTTP Resource for displaying connection in OpenNSA.

Currently rather simple.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012)
"""

from twisted.web import resource, server

from opennsa import database


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

    def __init__(self):
        pass

    def render_GET(self, request):

        d = database.ServiceConnection.find()
        d.addCallback(self.renderPage, request)
        return server.NOT_DONE_YET


    def renderPage(self, connections, request):

        ib = 4 * ' '

        body =''
        body += 2*ib + '<h3>Connections</h3>\n'
        body += 2*ib + '<p>\n'

        for c in connections:
            print c

            source = c.source_network + ':' + c.source_port + (':' + c.source_label.labelValue() if c.source_label else '')
            dest   = c.dest_network   + ':' + c.dest_port   + (':' + c.dest_label.labelValue()   if c.dest_label   else '')

            body += 2*ib + '<div>%s : %s | %s => %s | %s - %s</div>\n' % (c.connection_id, c.lifecycle_state, source, dest, c.start_time, c.end_time)
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

