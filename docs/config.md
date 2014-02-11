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
