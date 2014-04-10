OpenNSA configuration
---------------------


**Example configuration:**

```
[service]
network=Aruba
logfile=nsalog.log
topology=/home/htj/nsi/opennsa/local-topo.owl
#topology=/home/htj/nsi/opennsa/SC2011-Topo-v5f.owl
wsdl=/home/htj/nsi/opennsa/wsdl

[dud]

* Service block


network     : The network name managed by OpenNSA.
              Mandatory.

logfile     : File to log to.
              Defaults to /var/log/opennsa.log

topology    : Path to topology files.
              It is possible to have multiple topology files (handy for
              joining global and local topology) by specifying multiple
              topology files (comma-seperated). XML (RDF/OWL) and N3
              formats supported.
              Defaults to /usr/share/nsi/topology.owl

wsdl        : Directory for the wsdl files.
              Defaults to /usr/share/nsi/wsdl.
```


** NRM Configuration **

Configuration the nrm file is typically the most confusing parts of setting up
OpenNSA. In short the NRM file defines the ports available through the NSI
protocol, as OpenNSA does not make everything available. An NRM is line based
and typically looks like this:

```
# type      name    remote                              label               bandwith    interface   attributes

ethernet    ps      -                                   vlan:1780-1799,2000 1000        em0         user=johndoe@example.org
ethernet    bon     bonaire.net:topology#arb(-in|-out)  vlan:1780-1799      1000        em3         restricttransit


```

Each line describes a port.

* Type

The port type. Only ethernet is recognized at the moment. Bidirectional is implied here.

* Name

The name of the port. The port address will be a URN with the network and port name in it.

* Remote

The network and port the port is connected to. Format:

network#port(-inprefix|-outprefix)

Use '-' if not connected to any network (local termination port).

* Label

Port configuration options. Only VLANs supported for now. Can specify single values and ranges. Comma seperated.

Use '-' if no labels are to be used (i.e., trunk for vlan).

* Bandwidth

The available bandwidth on the port (or the bandwidth that is available to OpenNSA).

* Interface

The port on the corresponding NRM / network equipment. 

* Attributes

A list of comma seperated attributes that describes security attributes or
policies for the port. Security attributes always have the form 'key=value',
otherwise it is a policy. The only supported policy at the moment as
restricttransit (ports that both have restricttransit cannot be connected).

