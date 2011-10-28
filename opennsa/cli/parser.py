# Parser for the OpenNSA command-line tool.
#
# Commands: reserve, provision, release, terminate, query
#
# Flags:
# -u service url
# -t topology file

# -p provider nsa
# -r requester nsa

# -c connection id
# -g global reservation id

# -s source stp
# -d dest stp

# -n network

# Not all commands will accept all flags and some flags are mutally exclusive


from twisted.python import usage


# parameters

class ServiceURLOption(usage.Options):
    optParameters = [ ['service-url', 'u', None, 'Service URL'] ]

class ToplogyFileOption(usage.Options):
    optParameters = [ ['toplogy-file', 't', None, 'Topology File'] ]

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


# command options


class ReserveOptions(ServiceURLOption, ProviderNSAOption, RequesterNSAOption, SourceSTPOption, DestSTPOption):
    pass


class Options(usage.Options):
    subCommands = [
        ['reserve', None,   ReserveOptions, 'Create an NSI reservation']
    ]

    optFlags = [
        ['verbose', 'v', 'Print out more information']
    ]

    def postOptions(self):
        if self.subCommand is None:
            return usage.UsageError('No option specified')

    def opt_version(self):
        from twisted import copyright
        print "OpenNSA Development version. " + \
              "Running on Twisted version", copyright.version
        raise SystemExit

