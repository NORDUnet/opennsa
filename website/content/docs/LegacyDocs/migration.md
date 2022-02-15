---
categories: ["Legacy"]
tags: ["install"]
title: "Configuration Migration"
linkTitle: "Configuration Migration"
date: 2013-07-12
description: >
  Configuration Migration and py 2.x to 3.x changes
---
# OpenNSA 3 Configuration Migration


With the port of OpenNSA from Python 2 to Python 3, and the subsequent release
of OpenNSA 3, support for multiple backends was added. For this, some changes
in the configuration format was needed.

The changes are:
* Use domain instead of network in ```[service]``` block
* Each backend must specify a network name in its block
* NRM Map must now be specified per backend

Example of old style:

```ini
[service]
network=aruba.net
nrmmap=aruba.nrm

[dud]
```

Equivalent config in new style:

```ini
[service]
domain=aruba.net

[dud:topology]
nrmmap=aruba.nrm
```

An example with multiple backends shows why the change was needed:

```ini
[service]
domain=aruba.net

[dud:topology1]
nrmmap=aruba-topo1.nrm

[dud:topology1]
nrmmap=aruba-topo2.nrm
```

Feel free to call your networks something better than topology, but use
'topology' if you want to keep the old STP names.

