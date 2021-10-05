OpenNSA Docker
--------------

**Building Image**

$ make docker-build     ( from opennsa directory )


**Running Image**

As OpenNSA requires a Postgres database, docker-compose is used to coordinate
the setup of the two containers.

1. $ ./generate-docker-config
   This will mainly generate a password and create a .env file for you.  You may update the settings in .env if you wish to use a different nrm file (Keep in mind you'll need to mount it as a volume if you stray from the defaults or rebuild the image)

3. $ docker-compose up
   This should bring up a PostgreSQL instance and OpenNSA.

## Advanced Features

1.  In order to override any settings copy the docker-compose.override.yml_placeholder to docker-compose.override.yml.  You can use to mount additional volumes, expose additional ports etc.  Some common patterns are already there and commented out. 

2. Configuration options are almost all exposed via ENV variables.  If you wish to directly mount your config file, make a copy of config/opennsa.conf.template to config/opennsa.conf.  Update any entries as desired and restart all DB container.

3. The entry point is left as just bash, so if you wish to override the initial command you may simply set the `command:` line in your override file to anything you like.  If you want, you may also invoke the run_opennsa.sh with arguments, it will wait for the database to come up with run the command you issues.  

For example:   run_opennsa.sh sleep 50  ==> will wait for DB to come up then sleep for 50 seconds.