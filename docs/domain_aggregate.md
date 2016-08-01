Domain Aggregater Setup
=======================

This document brifly covers how to setup an OpenNSA instance as what is dubbed
"domain aggregator". That is, an OpenNSA instance running running in front of
several local OpenNSA instances.

The intended usage is that an organization has several OpenNSA (or other NSI
agents) running for different devcies and want to have a single frontend acting
as entry way for those agents. Furthermore the domain aggregator will be able
to aggregate with external NSAs, where the intent is that the NSI agents
controlling devices will be functioning as UPAs, i.e., be without aggregation
capability.


System Design
-------------

The UPA network names must be subdomains of the domain aggregator. Example:

Domain network id: `urn:ogf:network:aruba.net:topology`

The UPAs must have networks ids suchs as:

UPA network id: `urn:ogf:network:d1.aruba.net:topology`
UPA network id: `urn:ogf:network:d2.aruba.net:topology`

It is not possible to not adhere to this without modifying the code. The upside
of this is that by designing your network ids in a certain way you get rather
complex behaviour without complicated configuration.


Configuration
-------------

Configure the UPAs as usual, but make sure there is no `peers` entry. This will
ensure that they behave in a UPA fashion.

For the domain aggregator, set the policy for domain aggregation:

`policy=domainaggregate`

The peers list should contains the UPAs, and URLs to any other NSAs it should
be able to interact with. The domain aggregator should not have any backends
configured (it might work, but have not been tested).


Verification
------------

Retrieve the discovery file of the domain aggregator. It should list its own
netword id, along with the networks ids of the UPAs. This will make other NSI
agents think it is responsible for the network.


Caveats
-------

NML aliasing have not been implemented, which might be needed for this to
interoperate with some pathfinders.


