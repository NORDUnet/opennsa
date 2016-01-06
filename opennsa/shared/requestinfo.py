"""
DTO for passing information from the request across components/layers.

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2015-2016)
"""



class RequestInfo:
    """
    Holds various data about the request.
    Somewhat adding things as we go.
    """
    def __init__(self, cert_subject=None, cert_host_dn=None):
        self.cert_subject = cert_subject
        self.cert_host_dn = cert_host_dn

