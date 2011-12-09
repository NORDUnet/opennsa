# Parser for the OpenNSA command-line tool.
#
# Commands: reserve, provision, release, terminate, query
#
# Options:

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

# -b bandwidth (megabits)

# Flags
# (none currently)

# Not all commands will accept all flags and some flags are mutally exclusive


from twisted.python import usage


# constans, so we don't use strings in other modules

VERBOSE         = 'verbose'
DEFAULTS_FILE   = 'defaultsfile'
WSDL_DIRECTORY  = 'wsdldirectory'
HOST            = 'host'
PORT            = 'port'


# parameters used for all commands

class DefaultsFileOption(usage.Options):
    optParameters = [ [ DEFAULTS_FILE, 'f', None, 'Service URL'] ]

class WSDLDirectoryOption(usage.Options):
    optParameters = [ [ WSDL_DIRECTORY, 'w', None, 'Service URL'] ]

class HostOption(usage.Options):
    optParameters = [ [ HOST, 'h', None, 'Host (for callback)'] ]

class PortOption(usage.Options):
    optParameters = [ [ PORT, 'o', None, 'Port (for callback)'] ]

# parameters which are only used for some commands

class ServiceURLOption(usage.Options):
    optParameters = [ ['serviceurl', 'u', None, 'Service URL'] ]

class TopologyFileOption(usage.Options):
    optParameters = [ ['topologyfile', 't', None, 'Topology File'] ]

class NetworkOption(usage.Options):
    optParameters = [ ['network', 'n', None, 'Provider Network'] ]

class ProviderNSAOption(usage.Options):
    optParameters = [ ['provider', 'p', None, 'Provider NSA Identity'] ]

class RequesterNSAOption(usage.Options):
    optParameters = [ ['requester', 'r', None, 'Requester NSA Identity'] ]

class SourceSTPOption(usage.Options):
    optParameters = [ ['source-stp', 's', None, 'Source STP'] ]

class DestSTPOption(usage.Options):
    optParameters = [ ['dest-stp', 'd', None, 'Dest STP'] ]

class ConnectionIDOption(usage.Options):
    optParameters = [ ['connection-id', 'c', None, 'Connection id'] ]

class GlobalIDOption(usage.Options):
    optParameters = [ ['global-id', 'g', None, 'Global id'] ]

class StartTimeOption(usage.Options):
    optParameters = [ ['start-time', 'a', None, 'Start time'] ]

class EndTimeOption(usage.Options):
    optParameters = [ ['end-time', 'e', None, 'End time'] ]

class BandwidthOption(usage.Options):
    optParameters = [ ['bandwidth', 'b', None, 'Bandwidth (Megabits)'] ]


# command options


class ReserveOptions(ServiceURLOption, TopologyFileOption, NetworkOption, ProviderNSAOption, RequesterNSAOption, SourceSTPOption, DestSTPOption):

    def postOptions(self):
        if self['serviceurl'] and (self['topologyfile'] or self['network']):
            raise usage.UsageError('Cannot set both service url while having topology file or network.')



class Options(DefaultsFileOption, WSDLDirectoryOption, HostOption, PortOption):
    subCommands = [
        ['reserve', None,   ReserveOptions, 'Create an NSI reservation']
    ]

    optFlags = [
        [ VERBOSE, 'v', 'Print out more information']
    ]

    def postOptions(self):
        if self.subCommand is None:
            return usage.UsageError('No option specified')

    def opt_version(self):
        from twisted import copyright
        print "OpenNSA Development version. " + \
              "Running on Twisted version", copyright.version
        raise SystemExit

