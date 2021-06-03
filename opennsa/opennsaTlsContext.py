#!/usr/bin/env python
'''
The MIT License (MIT)
Copyright © 2021 SURF BV

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Author: Hans Trompert, SURF BV
'''

from OpenSSL import crypto
from os import listdir
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

        self._trustRoot = self._createTrustRootFromCADirectory(certificate_dir)
        self._extraCertificateOptions = {
            'enableSessions': False,
            'enableSessionTickets': False,
            'raiseMinimumTo': ssl.TLSVersion.TLSv1_2
        }
        if(not verify):
            log.msg('ignoring verify=false, WILL verify peer certificate against certdir', system = LOG_SYSTEM)

    def _createTrustRootFromCADirectory(self, certificate_dir):
        CACertificates = []
        for CAFilename in listdir(certificate_dir):
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
        return ssl.optionsForClientTLS(hostname, trustRoot=self._trustRoot, extraCertificateOptions=self._extraCertificateOptions)


class opennsa2WayTlsContext(opennsaTlsContext):
    """
    Full context with private key and certificate when running service
    over SSL/TLS.
    """
    def __init__(self, private_key_path, public_key_path, certificate_dir, verify):

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
        return ssl.optionsForClientTLS(hostname, trustRoot=self._trustRoot, clientCertificate=self._clientCertificate, extraCertificateOptions=self._extraCertificateOptions)

    def getOpenSSLCertificateOptions(self):
        return ssl.CertificateOptions(privateKey=self.getPrivateKey(), certificate=self.getCertificate(), trustRoot=self.getTrustRoot(),  **self.getExtraCertificateOptions())


def main():
    log.startLogging(stdout)
    opennsaContext = opennsa2WayTlsContext('server.key', 'server.crt', 'trusted_ca_s', False)
    log.msg('trustRoot = %s' % opennsaContext.getTrustRoot(), system = LOG_SYSTEM)
    log.msg('extraCertificateOptions = %s' % opennsaContext.getExtraCertificateOptions(), system = LOG_SYSTEM)
    log.msg('clientCertificate = %s' % opennsaContext.getClientCertificate().getSubject(), system = LOG_SYSTEM)
    log.msg('OpenSSLCertificateOptions = %s' % opennsaContext.getOpenSSLCertificateOptions(), system = LOG_SYSTEM)
    log.msg('ClientTLSOptions = %s' % opennsaContext.getClientTLSOptions('some.hostname'), system = LOG_SYSTEM)


if __name__ == "__main__":
    main()
