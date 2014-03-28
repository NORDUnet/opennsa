
# Ring topology in config format

ARUBA_TOPOLOGY = """
ethernet     ps      -                       vlan:1780-1789  1000    em0    -
ethernet     bon     bonaire#aru-(in|out)    vlan:1780-1789  1000    em1    -
ethernet     dom     dominica#aru-(in|out)   vlan:1780-1789   500    em2    -
"""

BONAIRE_TOPOLOGY = """
ethernet     ps      -                       vlan:1780-1789  1000    em0    -
ethernet     aru     aruba#bon-(in|out)      vlan:1780-1789  1000    em1    -
ethernet     cur     curacao#bon-(in|out)    vlan:1780-1789  1000    em2    -
ethernet     dom     dominica#bon-(in|out)   vlan:1781-1782   100    em3    -
"""

CURACAO_TOPOLOGY = """
ethernet     ps      -                       vlan:1780-1789  1000    em0    -
ethernet     bon     bonaire#cur-(in|out)    vlan:1780-1789  1000    em1    -
ethernet     dom     dominica#cur-(in|out)   vlan:1783-1786  1000    em2    -
"""

DOMINICA_TOPOLOGY = """
ethernet     ps      -                       vlan:1780-1789  1000    em0    -
ethernet     aru     aruba#dom-(in|out)      vlan:1780-1789  500     em1    -
ethernet     bon     bonaire#dom-(in|out)    vlan:1781-1782  100     em2    -
ethernet     cur     curacao#dom-(in|out)    vlan:1783-1786  1000    em3    -
"""

