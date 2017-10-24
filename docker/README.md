OpenNSA Docker
--------------

**Building Image**

$ make docker-build     ( from opennsa directory )


**Running Image**

As OpenNSA requires a Postgres database, docker-compose is used to coordinate
the setup of the two containers.

1. Edit opennsa.conf.template and opennsa.nrm
   Leave the database config as-is.

2. $ ./create-compose
   This will substitute stuff in the templates and create docker-compose.yml and opennsa.conf

3. $ docker-compose up
   This should bring up a PostgreSQL instance and OpenNSA.


You may have to edit template.yml to expose OpenNSA ports publically, mount in
certificates, or similar.


TODO: Make OpenNSA able to take database configuration via environment, so we
      don't have to do replacement in opennsa.conf

