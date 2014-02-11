Open NSA CLI
-----------

A short primer on the onsa command line tool.

Disclaimer: There are still bugs and unfinished functionality.

**Intro**

The onsa command line tools allows the creation of connections and basic
lifecycle management, along with query functionality.

If you cannot wait to get started, you can list the command options with:

    $ onsa --help

The command line tool requires a command (e.g., reserve or provision), and a
set of options, in order to carry out a command.


**Defaults file**

Often there will be a number of options, which will be the same or almost the
same with every invocation, e.g., location of topology files, WSDL directory,
identity of the client and so forth. To save time, the CLI will read on default
options from a file, typically ~/.opennsa-cli, but it is possible to specify an
alternate location using the -f (--defaults-file) option.

Here is an example of a `.opennsa-cli` defaults file:

```
topology=/home/htj/opennsa/SC2011-Topo-v5f.owl
wsdl=/home/htj/opennsa/wsdl
bandwidth=200
host=localhost
port=7080
starttime=+20
endtime=+260
```

Please note that currently, the character ~ is currently not expanded to the
users home directory. Relative paths should work, but that will constrain you
to a specific directory when using the tool, so it is recommended to use full
paths.

The host and port options, will be used in setting up the callback URL. They
will default to the value provided by "socket.getfqdn()" and 7080.

The starttime and endtime can be set to xsd datetime value, but can also be
assigned a +X value, with X being the number of seconds into the future. This
makes it easy to always get some usefull values when testing.

If an option is specified both on the command line and in the defaults file,
the command line value will be used.

It is possible to set all options which can be set on the command line in the
defaults file, with the exception of the command to perform.


**Using the tool**

With a default options file created, a connection can be created like this:

    $ ./onsa reserve --source northernlight.ets:ps-80 --dest northernlight.ets:ams-80 -n northernlight.ets 

A connection id and global id is assigned automatically but can also be
assigned using the -c and -g options.

To provision the connection:

    ./onsa provision -n northernlight.ets -c <connection-id>

Similarly with release and terminate, querysummary, and querydetails.

