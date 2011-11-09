"""
Simple SSL context factory.
"""
import os

from OpenSSL import SSL



class ContextFactory:
    """
    SSL context factory. Which hostkey and cert files to use,
    and which CA to load, etc.
    """
    def __init__(self, key_path, cert_path, ca_dir=None, verify=True):

        self.key_path = key_path
        self.cert_path = cert_path
        self.verify = verify
        self.ca_dir = ca_dir

        if self.verify and ca_dir is None:
            raise ValueError('Certificate directory must be specified')


    def getContext(self):
        # should probably implement caching sometime

        ctx = SSL.Context(SSL.SSLv23_METHOD) # this also allows tls 1.0
        ctx.set_options(SSL.OP_NO_SSLv2) # ssl2 is unsafe

        ctx.use_privatekey_file(self.key_path)
        ctx.use_certificate_file(self.cert_path)
        ctx.check_privatekey() # sanity check

        def verify_callback(conn, x509, error_number, error_depth, allowed):
            # just return what openssl thinks is right
            return allowed

        if self.verify:
            ctx.set_verify(SSL.VERIFY_PEER, verify_callback)

            calist = [ ca for ca in os.listdir(self.ca_dir) if ca.endswith('.0') ]
            for ca in calist:
                # openssl wants absolute paths
                ca = os.path.join(self.ca_dir, ca)
                ctx.load_verify_locations(ca)

        return ctx

