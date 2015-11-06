"""
HTTP Resource for displaying connection in OpenNSA.

Currently rather simple. No CSS, just raw html tables.

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

        body = """
        <h3>Connections</h3>
        <p>
        <table style="width:95%" border=1>
            <thead>
                <tr>
                    <th>Connection Id</th>
                    <th>Lifecycle state</th>
                    <th>Source</th>
                    <th>Destination</th>
                    <th>Start time</th>
                    <th>End time</th>
                </tr>
            </thead>
            <tbody>"""

        for c in connections:
            #print c

            source = c.source_network + ':' + c.source_port + (':' + c.source_label.labelValue() if c.source_label else '')
            dest   = c.dest_network   + ':' + c.dest_port   + (':' + c.dest_label.labelValue()   if c.dest_label   else '')

            start_time = c.start_time.replace(microsecond=0) if c.start_time is not None else '-'
            end_time = c.end_time.replace(microsecond=0)

            body += """
                 <tr>
                    <th><div>%s</div></th>
                    <th>%s</th>
                    <th>%s</th>
                    <th>%s</th>
                    <th>%s</th>
                    <th>%s</th>
                 </tr>
            """ % (c.connection_id, c.lifecycle_state, source, dest, start_time, end_time)

        body += 4*ib + '</tbody>'
        body += 3*ib + '</table>'

        body = str(body)

        request.write(HTML_HEADER % {'title': 'OpenNSA Connections'} )
        request.write(body)
        request.write(HTML_FOOTER)
        request.finish()
        return server.NOT_DONE_YET

