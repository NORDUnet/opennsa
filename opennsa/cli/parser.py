# Parser for the OpenNSA command-line tool.
#
# Commands: reserve, provision, release, terminate, query
#
# Options:

# -f defaults file

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

# -l certificate (signed public key)
# -k key (private key)
# -i certificate directory

# Flags
# -v verbose
# -q dump soap payloads
# -x Use TLS for callback port
# -z (skip) verify certificate (default is to verify)

# free switches
# ijmy + 0-9

# Not all commands will accept all flags and some flags are mutally exclusive


from twisted.python import usage

from opennsa.cli import options


# parameters used for all commands

class DefaultsFileOption(usage.Options):
    optParameters = [ [ options.DEFAULTS_FILE, 'f', None, 'Defaults file'] ]

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
    def postOptions(self):
        if self[options.START_TIME] is not None:
            self[options.START_TIME] = options.parseTimestamp( self[options.START_TIME] )

class EndTimeOption(usage.Options):
    optParameters = [ [ options.END_TIME, 'e', None, 'End time'] ]
    def postOptions(self):
        if self[options.END_TIME] is not None:
            self[options.END_TIME] = options.parseTimestamp( self[options.END_TIME] )

class BandwidthOption(usage.Options):
    optParameters = [ [ options.BANDWIDTH, 'b', None, 'Bandwidth (Megabits)'] ]

class PublicKeyOption(usage.Options):
    optParameters = [ [ options.CERTIFICATE, 'l', None, 'Certificate path' ] ]

class PrivateKeyOption(usage.Options):
    optParameters = [ [ options.KEY, 'k', None, 'Private key path' ] ]

class CertificateDirectoryOption(usage.Options):
    optParameters = [ [ options.CERTIFICATE_DIR, 'i', None, 'Certificate directory' ] ]

# flags

class TLSFlag(usage.Options):
    optFlags = [ [ options.TLS, 'x', 'Use TLS for listener port' ] ]

class SkipCertificateVerificationFlag(usage.Options):
    optFlags = [ [ options.VERIFY_CERT, 'z', 'Skip certificate verification' ] ]

class FullGraphFlag(usage.Options):
    optFlags = [ [ options.FULL_GRAPH, 'l', 'Render full graph with all links.' ] ]



# command options

class BaseOptions(DefaultsFileOption):

    optFlags = [
        [ options.VERBOSE, 'v', 'Print out more information'],
        [ options.DUMP_PAYLOAD, 'q', 'Dump message payloads'],
    ]


class NetworkBaseOptions(BaseOptions, HostOption, PortOption,
                         ServiceURLOption, TopologyFileOption, NetworkOption,
                         TLSFlag, PublicKeyOption, PrivateKeyOption, CertificateDirectoryOption, SkipCertificateVerificationFlag):

    def postOptions(self):
        # technically we should do this for all superclasses, but this is the only one that has anything to do
        if self[options.SERVICE_URL] and (self[options.TOPOLOGY_FILE] or self[options.NETWORK]):
            raise usage.UsageError('Cannot set service url while having topology file or network.')


class NetworkCommandOptions(NetworkBaseOptions, ProviderNSAOption, RequesterNSAOption, ConnectionIDOption, GlobalIDOption):
    pass


class DiscoveryOptions(NetworkBaseOptions):
    pass


class ReserveOptions(NetworkCommandOptions, SourceSTPOption, DestSTPOption, StartTimeOption, EndTimeOption, BandwidthOption):

    def postOptions(self):
        NetworkCommandOptions.postOptions(self)
        StartTimeOption.postOptions(self)
        EndTimeOption.postOptions(self)


class PathOptions(BaseOptions, SourceSTPOption, DestSTPOption, TopologyFileOption):
    pass


class TopologyOptions(BaseOptions, TopologyFileOption):
    pass


class TopologyGraphOptions(TopologyOptions, FullGraphFlag):
    pass


class ProvisionReleaseTerminateOptions(NetworkCommandOptions):
    pass


class Options(usage.Options):
    subCommands = [
        ['discover',        None,   DiscoveryOptions,       'Discover services at an NSA.'],
        ['reserve',         None,   ReserveOptions,         'Create a reservation.'],
        ['reserveprovision',None,   ReserveOptions,         'Create a reservation and provision the connection.'],
        ['provision',       None,   NetworkCommandOptions,  'Provision a connection.'],
        ['release',         None,   NetworkCommandOptions,  'Release a connection.'],
        ['terminate',       None,   NetworkCommandOptions,  'Terminate a connection.'],
        ['querysummary',    None,   NetworkCommandOptions,  'Query a connection (summary).'],
        ['querydetails',    None,   NetworkCommandOptions,  'Query a connection (recursive).'],
        ['path',            None,   PathOptions,            'Print possible paths from source STP to destination STP.'],
        ['topology',        None,   TopologyOptions,        'Print (known) topology information.'],
        ['topology-graph',  None,   TopologyGraphOptions,   'Print a machine parsable network topology (Graphviz).']
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


