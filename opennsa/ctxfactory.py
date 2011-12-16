"""
SSL/TLS context definition.

Most of this code is borrowed from the SGAS 3.X LUTS codebase.
NORDUnet holds the copyright for SGAS 3.X LUTS and OpenNSA.
"""

import os

from OpenSSL import SSL



class ContextFactory:

    def __init__(self, private_key_path, public_key_path, certificate_dir, verify=True):

        self.private_key_path   = private_key_path
        self.public_key_path    = public_key_path
        self.certificate_dir    = certificate_dir
        self.verify             = verify

        self.ctx = None


    def getContext(self):

        if self.ctx is not None:
            return self.ctx
        else:
            self.ctx = self._createContext()
            return self.ctx


    def _createContext(self):

        ctx = SSL.Context(SSL.TLSv1_METHOD) # only tls v1 (its almost 2012, should be okay

        ctx.use_privatekey_file(self.private_key_path)
        ctx.use_certificate_file(self.public_key_path)
        ctx.check_privatekey() # sanity check

        def verify_callback(conn, x509, error_number, error_depth, allowed):
            # just return what openssl thinks is right
            if self.verify:
                return allowed # return what openssl thinks is right
            else:
                return 1 # allow everything which has a cert

        ctx.set_verify(SSL.VERIFY_PEER, verify_callback)

        calist = [ ca for ca in os.listdir(self.certificate_dir) if ca.endswith('.0') ]
        for ca in calist:
            # openssl wants absolute paths
            ca = os.path.join(self.certificate_dir, ca)
            ctx.load_verify_locations(ca)

        return ctx

