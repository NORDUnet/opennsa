OpenNSA configuration
---------------------

# Example Configuration

```
[service]
network=Aruba
logfile=nsalog.log
nrmfile=ports.nrm

peers=http://host.example.org:9080/NSI/discovery.xml
      https://nsi.example.com/NSI/discovery.xml

policies=requiretrace,requireuser

serviceid_start=1900000

# Database
database=opennsa
dbuser=dbuser
dbpassword=dbpassword
dbhost=127.0.0.1

[dud]
option1=123
option2=abc
```

# Service block

These are the options for the service block:

`network`  : The network name managed by OpenNSA. Mandatory.

`logfile`  : File to log to. Default: /var/log/opennsa.log

`nrmmap`   : Path to port/topology NRM description file

`peers`    : URLs to NSAs to peer with control-plane wise.
             Seperate multiple entries with newline (only peers= on the first line).
             Optional. No peers will put OpenNSA into UPA mode.

`policies` : What policies are required. Currently `requiretrace`, `requireuser`,
             and `aggregator` are the possible options. These require a connection
             trace, a user security attribute, and allow proxy aggregation
             respecitively. Optional.

`serviceid_start` : Initial service id to set in the database. Requires a plugin
                    to use. Optional.

`database` : Name of the PostgreSQL databse to connect to. Mandatory.

`dbuser`   : Username to use when connecting to database. Mandatory.

`dbpassword` : Password to use when connecting to database. Mandatory.

`dbhost`   : Host to connect to for database. Optional. If not specificed,
             OpenNSA will connect to PostgreSQL over the unix domain socket
             OpenNSA does not require anything big from the datebase, so using a
             different host/vm is almost surely a waste of resources. It is
             however useful when running a PostgreSQL in docker.


# Backend

A backend is configured by a section describing the type of backend, e.g. `dud`
(for testing) or `junosmx`. The configuration options in the section are
specific to the backend. Reading the setup code in backend, is the easiest way
to see the options.


## Custom Backend

If you have written your own backend that is specific to an organization or
project, you can use the custombackend option:

```
[custombackend]
module=mycustombackend
op1=123
op2=abc
```

This will import the Python module named `mycustombackend` and pass along the
configuration options. You will probably need to specify PYTHONPATH to include
the path of the module.

It is strongly recommended that you keep the module out of the OpenNSA module
such that you can upgrade OpenNSA without having to re-deploy your backend.


# NRM Configuration

Configuration the nrm file is typically the most confusing parts of setting up
OpenNSA. In short the NRM file defines the ports available through the NSI
protocol, as OpenNSA does not make everything available. An NRM is line based
and typically looks like this:

```
# type      name    remote                              label               bandwith    interface   attributes

ethernet    ps      -                                   vlan:1780-1799,2000 1000        em0         user=johndoe@example.org
ethernet    bon     bonaire.net:topology#arb(-in|-out)  vlan:1780-1799      1000        em3         restricttransit
ethernet    cur     curacao.net:topology#arb(-in|-out)  vlan:1780-1799      1000        em3         restricttransit,hostdn=curacao.example.net

```

Each line describes an STP (NSI term). An STP is more or less the same as a
port. Note that two STPs can point to the same underlying interface / port,
which can occasionally be useful (you will probably know if this happens).
OpenNSA does reservations on the interface resources internally, to ensure that
resource do not get double booked.

## NRM Configuration options

`type`  : The port type. Only ethernet is recognized at the moment.
          Bidirectional is implied.

`name`  : The name of the STP. The STP address will be a URN with the network and name in it.

` Remote`   : The network and port the port is connected to. Format:
              `network#port(-inprefix|-outprefix)`
              Use '-' if not connected to any network (termination inside the network).

`label` : STP configuration options. Currently `vlan` and `mpls` are supported.
          Note that not all backend support those. Can specify single values and ranges. Comma seperated.
          Use '-' if no labels are to be used (i.e., ethernet trunk).

`bandwidth` : The available bandwidth on the port (or the bandwidth that is
              available to OpenNSA on the port).

`interface` : The interface / port on the network device.

`attributes` : A list of comma seperated attributes that describes security
               attributes or policies for the port. Security attributes always have the form
              `key=value`, otherwise it is a policy. Despite the name, security attributes
               are not very secure.

               The hostdn will match against the hostname of a certificate. For this to work
               OpenNSA must be configured to run with TLS (see docs/tls-guide).

               The only supported policy at the moment is `restricttransit`. If
               two ports both have the `restricttransit` attribute, connecions
               between the two will not be allowed.

