# Parser for the OpenNSA command-line tool.
#
# Commands: reserve, provision, release, terminate, query
#
# Options:

# -f defaults file

# -h host (for callback)
# -o port (for callback)

# -u service url
# -m auth header

# -t topology file  # no longer used
# -n network        # no longer used

# -p provider nsa
# -r requester nsa

# -c connection id
# -g global reservation id

# -s source stp
# -d dest stp
# -a start time
# -e end time
# -b bandwidth (megabits)

# -j security attributes
# -l certificate (signed public key)
# -k key (private key)
# -i certificate directory

# Flags
# -v verbose
# -q dump soap payloads
# -y Wait for notifications, exists on dataPlane deactivation and errorEvent
# -x Use TLS for callback port
# -z (skip) verify certificate (default is to verify)

# free switches
# 0-9

# Not all commands will accept all flags and some flags are mutally exclusive

import datetime

from twisted.python import usage

from opennsa.cli import options


# parameters used for all commands

class DefaultsFileOption(usage.Options):
    optParameters = [ [ options.DEFAULTS_FILE, 'f', None, 'Defaults file'] ]

class HostOption(usage.Options):
    optParameters = [ [ options.HOST, 'h', None, 'Host (for callback)'] ]

class PortOption(usage.Options):
    optParameters = [ [ options.PORT, 'o', None, 'Port (for callback)', int] ]

# parameters which are only used for some commands

class ServiceURLOption(usage.Options):
    optParameters = [ [ options.SERVICE_URL, 'u', None, 'Service URL'] ]

class AuthzHeaderOption(usage.Options):
    optParameters = [ [ options.AUTHZ_HEADER, 'm', None, 'Authorization header'] ]

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
    optParameters = [ [ options.START_TIME, 'a', None, 'Start time (UTC time)'] ]
    def postOptions(self):
        if self[options.START_TIME] is not None:
            self[options.START_TIME] = datetime.datetime.strptime(self[options.START_TIME], options.XSD_DATETIME_FORMAT) #.replace(tzinfo=None)

class EndTimeOption(usage.Options):
    optParameters = [ [ options.END_TIME, 'e', None, 'End time (UTC time)'] ]
    def postOptions(self):
        if self[options.END_TIME] is not None:
            self[options.END_TIME] = datetime.datetime.strptime(self[options.END_TIME], options.XSD_DATETIME_FORMAT) # .replace(tzinfo=None)

class SecurityAttributeOptions(usage.Options):
    optParameters = [ [ options.SECURITY_ATTRIBUTES, 'j', None, 'Security attributes (format attr1=value1,attr2=value2)'] ]
    def postOptions(self):
        sats = []
        if self[options.SECURITY_ATTRIBUTES]:
            for kv_split in self[options.SECURITY_ATTRIBUTES].split(','):
                if not '=' in kv_split:
                    raise usage.UsageError('No = in key-value attribute %s' % kv_split)
                key, value = kv_split.split('=',1)
                sats.append( (key, value) )
        self[options.SECURITY_ATTRIBUTES] = sats

class BandwidthOption(usage.Options):
    optParameters = [ [ options.BANDWIDTH, 'b', None, 'Bandwidth (Megabits)'] ]

class PublicKeyOption(usage.Options):
    optParameters = [ [ options.CERTIFICATE, 'l', None, 'Certificate path' ] ]

class PrivateKeyOption(usage.Options):
    optParameters = [ [ options.KEY, 'k', None, 'Private key path' ] ]

class CertificateDirectoryOption(usage.Options):
    optParameters = [ [ options.CERTIFICATE_DIR, 'i', None, 'Certificate directory' ] ]

# flags

class NotificationWaitFlag(usage.Options):
    optFlags = [ [ options.NOTIFICATION_WAIT, 'y', 'Wait for notifications, exists on data plane deactive and errorEvent' ] ]

class TLSFlag(usage.Options):
    optFlags = [ [ options.TLS, 'x', 'Use TLS for listener port' ] ]

class SkipCertificateVerificationFlag(usage.Options):
    optFlags = [ [ options.NO_VERIFY_CERT, 'z', 'Skip certificate verification' ] ]


# command options

class BaseOptions(DefaultsFileOption):

    optFlags = [
        [ options.VERBOSE, 'v', 'Print out more information'],
        [ options.DUMP_PAYLOAD, 'q', 'Dump message payloads'],
    ]


class NetworkBaseOptions(BaseOptions, HostOption, PortOption,
                         ServiceURLOption, AuthzHeaderOption, SecurityAttributeOptions,
                         TLSFlag, PublicKeyOption, PrivateKeyOption, CertificateDirectoryOption, SkipCertificateVerificationFlag):

    def postOptions(self):
        # technically we should do this for all superclasses, but these are the only ones that has anything to do
        SecurityAttributeOptions.postOptions(self)


class NetworkCommandOptions(NetworkBaseOptions, ProviderNSAOption, RequesterNSAOption, ConnectionIDOption, GlobalIDOption):
    pass


class ProvisionOptions(NetworkCommandOptions, NotificationWaitFlag):
    pass


class ReserveOptions(NetworkCommandOptions, SourceSTPOption, DestSTPOption, StartTimeOption, EndTimeOption, BandwidthOption):

    def postOptions(self):
        NetworkCommandOptions.postOptions(self)
        StartTimeOption.postOptions(self)
        EndTimeOption.postOptions(self)


class ReserveProvisionOptions(ReserveOptions, NotificationWaitFlag):
    pass


class ProvisionReleaseTerminateOptions(NetworkCommandOptions):
    pass


class Options(usage.Options):
    subCommands = [
        ['reserve',         None,   ReserveOptions,         'Create and commit a reservation.'],
        ['reserveonly',     None,   ReserveOptions,         'Create a reservation without comitting it.'],
        ['reservecommit',   None,   ProvisionOptions,       'Commit a held reservation.'],
        ['reserveprovision',None,   ReserveProvisionOptions,'Create a reservation and provision the connection.'],
        ['rprt',            None,   ReserveOptions,         'Create a reservation and provision, release and terminate the connection.'],
        ['provision',       None,   ProvisionOptions,       'Provision a connection.'],
        ['release',         None,   ProvisionOptions,       'Release a connection.'],
        ['terminate',       None,   NetworkCommandOptions,  'Terminate a connection.'],
        ['query',           None,   NetworkCommandOptions,  'Query a connection (provider summary).'],
        ['queryrec',        None,   NetworkCommandOptions,  'Query a connection (recursive).']
    ]

    def postOptions(self):
        if self.subCommand is None:
            return usage.UsageError('No option specified')


    def opt_version(self):
        from opennsa import __version__
        from twisted import copyright
        print("OpenNSA version %s. Running on Twisted version %s." % (__version__, copyright.version))
        raise SystemExit


