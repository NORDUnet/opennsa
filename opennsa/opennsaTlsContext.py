#!/usr/bin/env python
"""
SSL/TLS context definition.

Most of this code is borrowed from the SGAS 3.X LUTS codebase.
NORDUnet holds the copyright for SGAS 3.X LUTS and OpenNSA.

With contributions from Hans Trompert (SURF BV)
"""

from OpenSSL import crypto, SSL
from os import listdir, path
from sys import stdout
from twisted.internet import ssl
from twisted.python import log
from twisted.python.filepath import FilePath

LOG_SYSTEM = 'opennsaTlsContext'


class opennsaTlsContext:
    """
    Context to be used while issuing requests to SSL/TLS services without having
    a client certificate.
    """
    def __init__(self, certificate_dir, verify):

        self.certificate_dir = certificate_dir
        self.verify = verify
        self._trustRoot = self._createTrustRootFromCADirectory(certificate_dir)
        self._extraCertificateOptions = {
            'enableSessions': False,
            'enableSessionTickets': False,
            'raiseMinimumTo': ssl.TLSVersion.TLSv1_2,
            'fixBrokenPeers': True
        }

    def _createTrustRootFromCADirectory(self, certificate_dir):
        CACertificates = []
        for CAFilename in listdir(certificate_dir):
            if not CAFilename.endswith('.0'):
                continue
            CAFileContent = FilePath(certificate_dir).child(CAFilename).getContent()
            try:
                CACertificates.append(ssl.Certificate.loadPEM(CAFileContent))
            except crypto.Error as error:
                log.msg('Cannot load CA certificate from %s: %s' % (CAFilename, error), system = LOG_SYSTEM)
            else:
                log.msg('Loaded CA certificate commonName %s' % (str(CACertificates[-1].getSubject().commonName)), system = LOG_SYSTEM)
        if len(CACertificates) == 0:
            print('No certificiates loaded for CTX verificiation. CA verification will not work.')
        return ssl.trustRootFromCertificates(CACertificates)

    def getTrustRoot(self):
        return self._trustRoot

    def getExtraCertificateOptions(self):
        return self._extraCertificateOptions

    def getClientTLSOptions(self, hostname):
        if(not self.verify):
            log.msg('httpClient ignores verify=false, WILL verify certificate chain for %s against certdir' % (hostname), system = LOG_SYSTEM)
        return ssl.optionsForClientTLS(hostname, trustRoot=self._trustRoot, extraCertificateOptions=self._extraCertificateOptions)

    def getContext(self):
        if self.ctx is None:
            self.ctx = self.createOpenSSLContext()
        return self.ctx

    def createOpenSSLContext(self):

        log.msg('creating OpenSSL SSL Context ...', system=LOG_SYSTEM)

        def verify_callback(conn, x509, error_number, error_depth, allowed):
            # just return what openssl thinks is right
            if self.verify:
                return allowed # return what openssl thinks is right
            else:
                return 1 # allow everything which has a cert

        # The way to support tls 1.0 and forward is to use the SSLv23 method
        # (which means everything) and then disable ssl2 and ssl3
        # Not pretty, but it works
        ctx = SSL.Context(SSL.SSLv23_METHOD)
        ctx.set_options(SSL.OP_NO_SSLv2)
        ctx.set_options(SSL.OP_NO_SSLv3)

        # disable tls session id, as the twisted tls protocol seems to break on them
        ctx.set_session_cache_mode(SSL.SESS_CACHE_OFF)
        ctx.set_options(SSL.OP_NO_TICKET)

        ctx.set_verify(SSL.VERIFY_PEER, verify_callback)

        calist = [ ca for ca in listdir(self.certificate_dir) if ca.endswith('.0') ]
        if len(calist) == 0 and self.verify:
            log.msg('No certificiates loaded for CTX verificiation. CA verification will not work.', system=LOG_SYSTEM)
        for ca in calist:
            # openssl wants absolute paths
            ca = path.join(self.certificate_dir, ca)
            ctx.load_verify_locations(ca)

        return ctx


class opennsa2WayTlsContext(opennsaTlsContext):
    """
    Full context with private key and certificate when running service
    over SSL/TLS.
    """
    def __init__(self, private_key_path, public_key_path, certificate_dir, verify):

        self.private_key_path = private_key_path
        self.public_key_path = public_key_path
        self.ctx = None

        opennsaTlsContext.__init__(self, certificate_dir, verify)

        keyContent = FilePath(private_key_path).getContent()
        certificateContent = FilePath(public_key_path).getContent()
        self._clientCertificate = ssl.PrivateCertificate.loadPEM(keyContent + certificateContent)

    def getClientCertificate(self):
        return self._clientCertificate

    def getPrivateKey(self):
        return self.getClientCertificate().privateKey.original

    def getCertificate(self):
        return self.getClientCertificate().original

    def getClientTLSOptions(self, hostname):
        if(not self.verify):
            log.msg('httpClient ignores verify=false, WILL verify certificate chain for %s against certdir' % (hostname), system = LOG_SYSTEM)
        return ssl.optionsForClientTLS(hostname, trustRoot=self._trustRoot, clientCertificate=self._clientCertificate, extraCertificateOptions=self._extraCertificateOptions)

    def getContext(self):
        if self.ctx is None:
            self.ctx =  self.createOpenSSLContext()
        return self.ctx

    def createOpenSSLContext(self):

        self.ctx = opennsaTlsContext.createOpenSSLContext(self)

        log.msg('adding key and certificate to OpenSSL SSL Context ...', system=LOG_SYSTEM)
        self.ctx.use_privatekey_file(self.private_key_path)
        self.ctx.use_certificate_chain_file(self.public_key_path)
        self.ctx.check_privatekey() # sanity check

        return self.ctx


def main():
    log.startLogging(stdout)
    opennsaContext = opennsa2WayTlsContext('server.key', 'server.crt', 'trusted_ca_s', False)
    log.msg('trustRoot = %s' % opennsaContext.getTrustRoot(), system = LOG_SYSTEM)
    log.msg('extraCertificateOptions = %s' % opennsaContext.getExtraCertificateOptions(), system = LOG_SYSTEM)
    log.msg('clientCertificate = %s' % opennsaContext.getClientCertificate().getSubject(), system = LOG_SYSTEM)
    log.msg('OpenSSLContext = %s' % opennsaContext.getContext(), system = LOG_SYSTEM)
    log.msg('ClientTLSOptions = %s' % opennsaContext.getClientTLSOptions('some.hostname'), system = LOG_SYSTEM)


if __name__ == "__main__":
    main()
