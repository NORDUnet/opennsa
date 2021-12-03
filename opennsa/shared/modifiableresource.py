"""
twisted.web.resource.Resource that supports the if-modified-since header.
Currently only leaf behaviour is supported.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2013-2014)
"""
import datetime

from twisted.web import resource


RFC850_FORMAT       = '%a, %d %b %Y %H:%M:%S GMT'
CONTENT_TYPE        = 'Content-type'
LAST_MODIFIED       = 'Last-modified'
IF_MODIFIED_SINCE   = 'if-modified-since'



class ModifiableResource(resource.Resource):

    isLeaf = True

    def __init__(self, log_system, mime_type=None):

        resource.Resource.__init__(self)

        self.log_system = log_system
        self.mime_type = mime_type

        self.updateResource(None) # so we always have something, resource generate an error though


    def updateResource(self, representation, update_time=None):
        # if no update time is given the current time will be used
        self.representation = representation
        if update_time is None:
            update_time = datetime.datetime.utcnow().replace(microsecond=0)

        self.last_update_time = update_time
        self.last_modified_timestamp = datetime.datetime.strftime(update_time, RFC850_FORMAT)


    def render_GET(self, request):

        if self.representation is None:
            # we haven't been given a representation yet
            request.setResponseCode(500)
            return b'Resource has not yet been created/updated.'

        # check for if-modified-since header, and send 304 back if it is not been modified
        msd_header = request.getHeader(IF_MODIFIED_SINCE)
        if msd_header:
            try:
                msd = datetime.datetime.strptime(msd_header, RFC850_FORMAT)
                if msd >= self.last_update_time:
                    request.setResponseCode(304)
                    return b''
            except ValueError:
                pass # error parsing timestamp

        request.setHeader(LAST_MODIFIED, self.last_modified_timestamp)
        if self.mime_type:
            request.setHeader(CONTENT_TYPE, self.mime_type)

        return self.representation

