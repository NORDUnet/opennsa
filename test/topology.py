
# Ring topology in config format

ARUBA_TOPOLOGY = """
bi-ethernet     ps      -                       vlan:1780-1789  1000    em0
bi-ethernet     bon     bonaire#aru-(in|out)    vlan:1780-1789  1000    em1
bi-ethernet     dom     dominica#aru-(in|out)   vlan:1780-1789   500    em2
"""

BONAIRE_TOPOLOGY = """
bi-ethernet     ps      -                       vlan:1780-1789  1000    em0
bi-ethernet     aru     aruba#bon-(in|out)      vlan:1780-1789  1000    em1
bi-ethernet     cur     curacao#bon-(in|out)    vlan:1780-1789  1000    em2
bi-ethernet     dom     dominica#bon-(in|out)   vlan:1781-1782   100    em3
"""

CURACAO_TOPOLOGY = """
bi-ethernet     ps      -                       vlan:1780-1789  1000    em0
bi-ethernet     bon     bonaire#cur-(in|out)    vlan:1780-1789  1000    em1
bi-ethernet     dom     dominica#cur-(in|out)   vlan:1783-1786  1000    em2
"""

DOMINICA_TOPOLOGY = """
bi-ethernet     ps      -                       vlan:1780-1789  1000    em0
bi-ethernet     aru     aruba#dom-(in|out)      vlan:1780-1789  500     em1
bi-ethernet     bon     bonaire#dom-(in|out)    vlan:1781-1782  100     em2
bi-ethernet     cur     curacao#dom-(in|out)    vlan:1783-1786  1000    em3
"""

