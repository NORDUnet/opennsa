# Parser for the OpenNSA command-line tool.
#
# Commands: reserve, provision, release, terminate, query
#
# Options:

# -v verbose
# -f defaults file
# -w wsdl directory

# -h host (for callback)
# -o port (for callback)

# -u service url

# -t topology file
# -n network

# -p provider nsa
# -r requester nsa

# -c connection id
# -g global reservation id

# -s source stp
# -d dest stp
# -a start time
# -e end time
# -b bandwidth (megabits)

# -l public key
# -k private key
# -i certificate directory

# Flags
# -z (skip) verify certificate (default is to verify)

# free switches
# ijmxyz

# Not all commands will accept all flags and some flags are mutally exclusive


from twisted.python import usage

from opennsa.cli import options


# parameters used for all commands

class DefaultsFileOption(usage.Options):
    optParameters = [ [ options.DEFAULTS_FILE, 'f', None, 'Service URL'] ]

class WSDLDirectoryOption(usage.Options):
    optParameters = [ [ options.WSDL_DIRECTORY, 'w', None, 'Service URL'] ]

class HostOption(usage.Options):
    optParameters = [ [ options.HOST, 'h', None, 'Host (for callback)'] ]

class PortOption(usage.Options):
    optParameters = [ [ options.PORT, 'o', None, 'Port (for callback)'] ]

# parameters which are only used for some commands

class ServiceURLOption(usage.Options):
    optParameters = [ [ options.SERVICE_URL, 'u', None, 'Service URL'] ]

class TopologyFileOption(usage.Options):
    optParameters = [ [ options.TOPOLOGY_FILE, 't', None, 'Topology File'] ]

class NetworkOption(usage.Options):
    optParameters = [ [ options.NETWORK, 'n', None, 'Provider Network'] ]

class ProviderNSAOption(usage.Options):
    optParameters = [ [ options.PROVIDER, 'p', None, 'Provider NSA Identity'] ]

class RequesterNSAOption(usage.Options):
    optParameters = [ [ options.REQUESTER, 'r', None, 'Requester NSA Identity'] ]

class SourceSTPOption(usage.Options):
    optParameters = [ [ options.SOURCE_STP, 's', None, 'Source STP'] ]

class DestSTPOption(usage.Options):
    optParameters = [ [ options.DEST_STP, 'd', None, 'Dest STP'] ]

class ConnectionIDOption(usage.Options):
    optParameters = [ [ options.CONNECTION_ID, 'c', None, 'Connection id'] ]

class GlobalIDOption(usage.Options):
    optParameters = [ [ options.GLOBAL_ID, 'g', None, 'Global id'] ]

class StartTimeOption(usage.Options):
    optParameters = [ [ options.START_TIME, 'a', None, 'Start time'] ]

class EndTimeOption(usage.Options):
    optParameters = [ [ options.END_TIME, 'e', None, 'End time'] ]

class BandwidthOption(usage.Options):
    optParameters = [ [ options.BANDWIDTH, 'b', None, 'Bandwidth (Megabits)'] ]

class PublicKeyOption(usage.Options):
    optParameters = [ [ options.PUBLIC_KEY, 'l', None, 'Public key path' ] ]

class PrivateKeyOption(usage.Options):
    optParameters = [ [ options.PRIVATE_KEY, 'k', None, 'Private key path' ] ]

class CertificateDirectoryOption(usage.Options):
    optParameters = [ [ options.CERTIFICATE_DIR, 'i', None, 'Certificate directory' ] ]

# flags

class SkipCertificateVerificationFlag(usage.Options):
    optFlags = [ [ options.SKIP_CERT_VERIFY, 'z', 'Skip certificate verification' ] ]


# command options

class NetworkCommandOptions(DefaultsFileOption, WSDLDirectoryOption, HostOption, PortOption,
                            ServiceURLOption, TopologyFileOption, NetworkOption,
                            ProviderNSAOption, RequesterNSAOption, ConnectionIDOption, GlobalIDOption,
                            PublicKeyOption, PrivateKeyOption, CertificateDirectoryOption, SkipCertificateVerificationFlag):

    optFlags = [
        [ options.VERBOSE, 'v', 'Print out more information']
    ]

    def postOptions(self):
        if self[options.SERVICE_URL] and (self[options.TOPOLOGY_FILE] or self[options.NETWORK]):
            raise usage.UsageError('Cannot set both service url while having topology file or network.')


class ReserveOptions(NetworkCommandOptions, SourceSTPOption, DestSTPOption, StartTimeOption, EndTimeOption, BandwidthOption):
    pass


class ProvisionReleaseTerminateOptions(NetworkCommandOptions):
    pass


class Options(usage.Options):
    subCommands = [
        ['reserve',         None,   ReserveOptions,         'Create a reservation'],
        ['reserveprovision',None,   ReserveOptions,         'Create a reservation and provision the connection.'],
        ['provision',       None,   NetworkCommandOptions,  'Provision a connection.'],
        ['release',         None,   NetworkCommandOptions,  'Release a connection.'],
        ['terminate',       None,   NetworkCommandOptions,  'Terminate a connection.'],
        ['querysummary',    None,   NetworkCommandOptions,  'Query a connection (summary).'],
        ['querydetails',    None,   NetworkCommandOptions,  'Query a connection (recursive).']
    ]

    def postOptions(self):
        if self.subCommand is None:
            return usage.UsageError('No option specified')


    def opt_version(self):
        from opennsa import __version__
        from twisted import copyright
        print "OpenNSA version %s. " % __version__ + \
              "Running on Twisted version", copyright.version
        raise SystemExit


