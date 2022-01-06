---
categories: ["Developer"]
tags: ["install", "developer"]
title: "Quick Developer Guide"
linkTitle: "Quick Developer Guide"
date: 2021-12-16
description: >
  Quick Developer Guide
---
# Quick Developer Guide


## Server Setup

For this guide we are assuming you are using the configuration templates and examples provided by default.  Any commands
will likely need to be updated accordingly for your own topology and configuration.

We'll assume that you are either running the server locally.  Both of those cases will require a running postgres database.  For simplicity sake I'm going to assume you have a docker-compose stack running.  

```
./generate-docker-config  ## will create a .env file and config/opennsa.conf
docker-compose up -d 
```
## Usage Guide

All operations in this case will be triggered via the client titled onsa which can be found in the root of the project.

There are a few 'base' operation that are supported by the Network Service Interface (NSI) Spec which you can find [here](GFD.237.pdf).  Others that are not listed in the document serve as a convenience method.

All operation are usually a sequence of: reserve, reserveCommit, provision, release, terminate.
query related requests are for diagnostic purposes.

### Endpoints

The following endpoints will then be accessible if everything works as advertised.

  - http://localhost:9080/NSI/dockertest.net:2021:topology.nml.xml
  - http://localhost:9080/NSI/discovery.xml


### Step 0 NSI Domain knowledge

#### Assumptions:

  - TLS is not enabled.
  - running locally and exposed 9080 locally.
  - hostname is set to dockertest.net:2021 or similar value in the format of:

```
{domain_name}:year
```

In our example and sample file we use `dockertest.net:2021`

#### URN

All resources are mapped using a URN pattern.  

http://localhost:9080/NSI/dockertest.net:2021:topology.nml.xml will show you your current topology.

Resources are reference by URN which are in the following format:

`<prefix>:<organization>:<type>`  example value is: `urn:ogf:network:dockertest.net:2021:topology:ps#vlan=1780`

 - prefix:  should be `urn:ogf:network`
 - organization: <domain_name>:year
 - type: in our example would `topology`
 - resource: <name>#<label={vlan or mpls}>=<ID aka 1780>
 
More info can be found in the [config](config.md) documentation.

#### Selecting Source / Destination

## Reservation: Step 1

NOTES: Currently the -s and -d strip away the prefix.  Please be aware when using the CLI client.

```sh
onsa reserve \
    -u http://localhost:9080/NSI/services/CS2 \  ##service from Docker 
    -g urn:uuid:d7a6a2ff-2cb5-4892-8bec-2a50140a6342 \ ##Global ID
    -s "dockertest.net:2021:topology:ps#vlan=1780" \  ## Source
    -d "dockertest.net:2021:topology:port1#vlan=1787" \  ## Destination
    -b 100 \  # bandwidth in Megabits
    -a 2022-09-24T20:00:00 \  #start date/time (has to be in the future)
    -e 2022-09-24T21:00:00 \  ## end date/time (again in the future)
    -p dockertest.net:2021:nsa \  ## provider
    -r dockertest.net:2021:sense \ ##requested 
    -h 192.168.1.64 \  ## OpenNSA Server host (localhost won't work if using docker)
    -o 8543 \  #Port 
    -v \  ## verbose
    -q ##dump payload message
```

### Query Validation

We're going to query the data for the reservation we just created.

```sh
 ./onsa query \ 
 -u http://localhost:9080/NSI/services/CS2  \ 
 -p "dockertest.net:2021:nsa"  \
 -r "dockertest.net:2021:sense" \
 -h 192.168.1.64 -o 8543 \
 -q
```

Output:

```
Connection   DO-8108e03315 (urn:ogf:network:dockertest.net:2021:nsa)
Global ID    urn:uuid:d7a6a2ff-2cb5-4892-8bec-2a50140a6342
Description  Test Connection
States       ReserveStart, Released, Created
Dataplane    Active : False, Version: 0, Consistent False
Start-End    2022-09-24 20:00:00 - 2022-09-24 21:00:00
Path         dockertest.net:2021:topology:ps?vlan=1780 -- dockertest.net:2021:topology:port1?vlan=1787
Bandwidth    100
Direction    Bidirectionall
```

## Provision Step 2

We'll need the Connection ID from the query above for this step.

```sh
./onsa provision \ 
    -c  DO-8108e03315 \  ## Connection 
    -u http://localhost:9080/NSI/services/CS2 \
    -p "dockertest.net:2021:nsa" \
    -r "dockertest.net:2021:sense" \
    -h 192.168.1.64 -o 8543 \
    -v -q
```

Same Query as above should now show a new state of: 

```
States       **ReserveHeld**, Provisioning, Created
```

# Clean up Operations

## Release Step 3 

```sh
./onsa release \ 
    -c  DO-8108e03315 \  
    -u http://localhost:9080/NSI/services/CS2 \
    -p "dockertest.net:2021:nsa" \
    -r "dockertest.net:2021:sense" \
    -h 192.168.1.64 -o 8543 \
    -v -q
```

## Terminate Step 4

```sh
./onsa terminate \ 
    -c  DO-8108e03315 \ 
    -u http://localhost:9080/NSI/services/CS2 \
    -p "dockertest.net:2021:nsa" \ 
    -r "dockertest.net:2021:sense" \
    -h localhost -o 8543 \
    -v -q
``` 


