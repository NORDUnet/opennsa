"""
Module for constants in OpenNSA.

Often the same constants are used in multiple modules where one does not want
cross-imports, like protocols/nsi2 and topology. This module gives a place to
keep them all. While not being particularly elegant it does solve a real
problem.

It is recommend to import this module as 'cnt' to keep the prefix short, but
also the same in the code base.
"""


URN_OGF_PREFIX      = 'urn:ogf:network:'

CS2_SERVICE_TYPE    = 'application/vnd.org.ogf.nsi.cs.v2+soap'
NML_SERVICE_TYPE    = 'application/vnd.ogf.nsi.topology.v2+xml'

CS2_REQUESTER       = 'application/vnd.ogf.nsi.cs.v2.requester+soap'
CS2_PROVIDER        = 'application/vnd.ogf.nsi.cs.v2.provider+soap'

BIDIRECTIONAL       = 'Bidirectional'

EVTS_AGOLE          = 'http://services.ogf.org/nsi/2013/07/descriptions/EVTS.A-GOLE'

ETHERNET_NS         = 'http://schemas.ogf.org/nml/2012/10/ethernet'
NML_ETHERNET_VLAN   = '%s#vlan' % ETHERNET_NS

ETHERNET_VLAN       = 'vlan'

NRM_ETHERNET        = 'ethernet' # bidirectional implied
NRM_RESTRICTTRANSIT = 'restricttransit'

FEATURE_AGGREGATOR  = 'vnd.ogf.nsi.cs.v2.role.aggregator'
FEATURE_UPA         = 'vnd.ogf.nsi.cs.v2.role.uPA'

REQUIRE_USER        = 'requireuser'
REQUIRE_TRACE       = 'requiretrace'

