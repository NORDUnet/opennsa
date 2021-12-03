# OpenNSA Installation Notes

This document covers the requirements, dependencies, installation and
configuration of OpenNSA.

## Overview

OpenNSA is a single Python process that listens on one port.
It uses PostgreSQL for storage.
Requires outbound connectivity to talk to other NSI agents.
Requires access to connect to the devices to setup cross-connects.
Doesn't need to run as root.

## Requirements:

Host OS:

Ubuntu/Debian is the easiest. RedHat/Fedora will work too. I suspect you can
make it work on any Linux that can run Python 2.7 and PostgreSQL. Several
people have had it running on OS X.

It runs fine in a virtual machine. Real iron be fine as well (but a bit wasteful).

Server location:

As close to the router/device for obvious reasons, but it is not latencey
sensitive or anything. Next city should also work.

Dmz vs. behind the firewall: Should work with both, not required.


## Dependencies:

* Python 3 

* Twisted 21.x.x or later, http://twistedmatrix.com/trac/

* Psycopg 2.9.0 or later (http://initd.org/psycopg/)

* Twistar 2.0 or later (https://pypi.python.org/pypi/twistar/ & http://findingscience.com/twistar/ )

* PostgreSQL (need 12 or later if using connection id assignment)

* pyOpenSSL 17.5 or later (when running with SSL/TLS)

Python and Twisted should be included in the package system in most recent
Linux distributions.

If you see connection lost for ssh in the log, most likely your Twisted version is too old.

Furthermore, for SSH based backends (Brocade, Force10, and Juniper), the
packages pyasn1 and python-crypto are also required.

If you use a backend which uses SSH (JunOS, Force10), there is a patch to
remove some of the log statements in the Twisted SSH module, which is rather
noisy. This makes the log a lot easier to read.

For users of equipment with old SSH services that does not support using SHA-2
hashing (and this require SHA-1 hashing), there is patch in the patches
directory for adding that support to Twisted.


## Installation:

python setup.py build
sudo python setup.py install


## Database setup:

You need to have a postgresql database setup and the user should have access to
it (if you use OS access - which is the easiest - you can put whatever in the
password field, it isn't used). Usually like this: 

$ su - postgres
$ createdb opennsa
$ createuser opennsa
$ exit
$ psql opennsa # as the user that runs opennsa
$ \i datafiles/schema.sql


## Configuration:

Edit /etc/opennsa.conf. Configuring the service is relatively straightforward,
but creating the topology specification is still somewhat tricky. Look at the
.nrm file in opennsa distribution for an example.


## Command line tool:

Make a reservation:
onsa reserve -u http://localhost:9080/NSI/services/ConnectionService -p OpenNSA-TestClient -r Aruba -s Aruba:A1 -d Aruba:A4

Do a ./onsa --help for more information.


## Development

To start a test service:

twistd -noy opennsa.tac

Note that opennsa.conf must exists in the source directory for this to work.

