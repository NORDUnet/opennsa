Installing OpenNSA on CentOS 6.4
--------------------------------
* Date: July 12 2013
* Authors: Henrik Jensen/Nordu.net and Jeronimo Bezerra/AMPATH
* Version: 1.1

1) Upgrade the CentOS 6.4:

    yum update

2) Install PostgreSQL Server and its development dependencies:

    yum install postgresql-server.x86_64 postgresql-plpython.x86_64 postgresql-devel.x86_64

3) Install Python 2.7 (CentOS depends of Python2.6 for its package system)

    yum groupinstall "Development tools"
    yum install zlib-devel bzip2-devel openssl-devel ncurses-devel sqlite-devel readline-devel tk-devel
    cd /usr/local/src
    wget http://python.org/ftp/python/2.7.3/Python-2.7.3.tar.bz2
    tar xf Python-2.7.3.tar.bz2
    cd Python-2.7.3
    ./configure --prefix=/usr/local
    make && make altinstall

The Python2.7 interpreter is at /usr/local/bin/python2.7

4) Install the Python Distribute

    wget --no-check-certificate http://pypi.python.org/packages/source/d/distribute/distribute-0.6.35.tar.gz
    tar xf distribute-0.6.35.tar.gz
    cd distribute-0.6.35
    python2.7 setup.py install

 This generates the script /usr/local/bin/easy_install-2.7 that you use to install packages for Python 2.7.
 It puts your packages in /usr/local/lib/python2.7/site-packages/

5) Install python-dateutil

    wget http://labix.org/download/python-dateutil/python-dateutil-1.5.tar.gz
    easy_install-2.7 python-dateutil-1.5.tar.gz

6) Install Twisted

    wget --no-check-certificate https://pypi.python.org/packages/source/T/Twisted/Twisted-13.1.0.tar.bz2#md5=5609c91ed465f5a7da48d30a0e7b6960
    easy_install-2.7 Twisted-13.1.0.tar.bz2

7) Install Twistar-1.2

    wget --no-check-certificate https://pypi.python.org/packages/source/t/twistar/twistar-1.2.tar.gz#md5=4f63af14339b1f2d9556395b527ea7a4
    easy_install-2.7 twistar-1.2.tar.gz

8) Install psycopg

    wget http://initd.org/psycopg/tarballs/PSYCOPG-2-5/psycopg2-2.5.1.tar.gz
    easy_install-2.7 psycopg2-2.5.1.tar.gz

9) Install pycrypto-2.6 and pyasn1-0.1.7 (only necessary when using SSH backends)

    wget --no-check-certificate https://pypi.python.org/packages/source/p/pycrypto/pycrypto-2.6.tar.gz
    easy_install-2.7 pycrypto-2.6.tar.gz
 
    wget --no-check-certificate https://pypi.python.org/packages/source/p/pyasn1/pyasn1-0.1.7.tar.gz#md5=2cbd80fcd4c7b1c82180d3d76fee18c8
    easy_install-2.7 pyasn1-0.1.7.tar.gz
 
10) Initialize and Start the PostgreSQL

    service postgresql initdb
    service postgresql start

    ln -s /etc/init.d/postgresql /etc/rc3.d/S99postgresql
    ln -s /etc/init.d/postgresql /etc/rc3.d/K99postgresql

11) Prepare the environment for Opennsa

    useradd opennsa
    su - opennsa

12) Install OpenNSA

    git clone git://git.nordu.net/opennsa.git
    cd opennsa
    git checkout nsi2
    python2.7 setup.py build
    su
    python2.7 setup.py install
 
13) Create the database

    cp datafiles/schema.sql /tmp/
    su - postgres
    createdb opennsa
    createuser -RSD opennsa 
    exit
    su - opennsa
    psql opennsa
    opennsa=# \i /tmp/schema.sql
    exit
    <CTRL+D>
    exit

14) It's important to keep the server time accurate (NTP)

    yum install ntp.x86_64
    ln -s /etc/init.d/ntpd /etc/rc3.d/S99ntpd
    ln -s /etc/init.d/ntpd /etc/rc3.d/K99ntpd
    /etc/init.d/ntpd start

15) Generate your SSH keys

    su - opennsa
    ssh-keygen
 

 Press <ENTER> 3 times. The keys `id_dsa` and `id_dsa.pub` will be created under `~opennsa/.ssh/`
 
 They key needs to have this format for Twisted recognizes it:
 
 ssh-rsa pub-key(3 or more lines) user@server.ampath.net
 
16) Edit these two configuration files accordingly to your environment (under /home/opennsa/opennsa):

    vi opennsa.conf

```
 [service]
 network=<YOUR_NETWORK_NAME>
 logfile=
 nrmmap=opennsa.nrm
 host=<SERVER_FQDN>
 database=opennsa
 dbuser=opennsa
 dbpassword=<YOUR_PASS>
 tls=false

 # vi opennsa.nrm (your topology)

 # type          name        remote                labels              bandwith    interface
 #
 # Assuming that my IXP is IXP_A, follow an example:
 #
 # AMPATH <-- 2/2 IXP_A 2/1 --> NORDUNET
 #
 # bi-ethernet   nordunet    nordunet#IXP_A-(in|out) vlan:1779-1787      1000        2/1
 # bi-ethernet   ampath      ampath#IXP_A-(in|out)   vlan:1779-1787      1000        2/2
 #
 # type          name        remote        labels              bandwith    interface
 bi-ethernet     <REMOTE_1>  <REMOTE_1>#<YOUR_NETWORK>-(in|out) vlan:1779-1787      1000        <DEVICE_PORT_1>
 bi-ethernet     <REMOTE_2>  <REMOTE_2>#<YOUR_NETWORK>-(in|out) vlan:1779-1787      1000        <DEVICE_PORT_2>
 bi-ethernet     <REMOTE_3>  <REMOTE_3>#<YOUR_NETWORK>-(in|out) vlan:1779-1787      1000        <DEVICE_PORT_3>
```



17) Create a `.opennsa-cli` file under `~opennsa/`

    echo -e "bandwidth=200\nhost=localhost\nport=7080\nstarttime=+1\nendtime=+20" > ~opennsa/.opennsa-cli
 
 The starttime and the endtime represent when the circuit will start and end in seconds

18) Configure your backend in the opennsa.conf

```
 # OpenNSA has support for the following backends: brocade, dell, etc...
 # So create a section for your backend with the following format:
 #
 [backend_type]
 host=x.x.x.x
 user=opennsa
 fingerprint=xx:xx:xx:xx:xx:xx:xx...
 publickey=/home/opennsa/.ssh/id_rsa.pub
 privatekey=/home/opennsa/.ssh/id_rsa

 # if your backend is Brocade, an example:
 #
 [brocade]
 host=x.x.x.x
 user=opennsa
 fingerprint=xx:xx:xx:xx:xx:xx:xx....
 publickey=/home/opennsa/.ssh/id_rsa.pub
 privatekey=/home/opennsa/.ssh/id_rsa
 enablepassword=XXXXX
```

19) Start the OpenNSA:

    su - opennsa
    cd opennsa
    twistd -ny opennsa.tac
    (-n to not create a daemon. There is also an init.d script)

 You should see:

``` 
 2013-07-02 14:17:08-0400 [-] Log opened.
 2013-07-02 14:17:08-0400 [-] twistd 13.1.0 (/usr/local/bin/python2.7 2.7.3) starting up.
 2013-07-02 14:17:08-0400 [-] reactor class: twisted.internet.epollreactor.EPollReactor.
 2013-07-02 14:17:08-0400 [-] OpenNSA service initializing
 2013-07-02 14:17:08-0400 [-] Provider URL: http://<SERVER_FQDN>:9080/NSI/services/CS2
 2013-07-02 14:17:08-0400 [-] Topology URL: http://<SERVER_FQDN>:9080/NSI/topology/<YOUR_NETWORK>.xml
 2013-07-02 14:17:08-0400 [-] Site starting on 9080
 2013-07-02 14:17:08-0400 [-] Starting factory <twisted.web.server.Siteinstance at 0x1df39e0>
 2013-07-02 14:17:08-0400 [-] OpenNSA service started
```

20) Configure your network device to support authentication using SSH keys

 In general, you have to copy your public key (id_dsa.pub) to the network device
 and insert this key in the valid users key chain. Check your device's documentation to confirm how to make this  
 configuration.
 
 As an example, in Brocade MLX switches you have to:

```
 a. cd ~opennsa/.ssh
 b. echo "---- BEGIN SSH2 PUBLIC KEY ----" > keys.txt
 c. cat id_dsa.pub >> keys.txt
 d. echo "---- END SSH2 PUBLIC KEY ----" >> keys.txt
 e. Remove the encryption algorithm (ssh-rsa):  sed -i 's/ssh-rsa //'keys.txt
 d. Remove the user (opennsa@<SERVER_FQDN>): sed -i 's/opennsa@<SERVER_FQDN>//' keys.txt
 f. Upload the keys.txt to your TFTP server
 g. Log into your Brocade device and:
 g1. SSH@Brocade# configure terminal
 g2. SSH@Brocade(config)# ip ssh pub-key-file tftp <TFTP_SERVER> keys.txt
 g3. SSH@Brocade(config)# ip ssh key-authentication yes
 g4. SSH@Brocade(config)# end
 g5. SSH@Brocade# write memory
```

21) Now you are ready to run OpenNSA

 Use the document docs/usage for understand how to use it (under development).

References:
 
* https://github.com/NORDUnet/opennsa/blob/nsi2/INSTALL
* http://toomuchdata.com/2012/06/25/how-to-install-python-2-7-3-on-centos-6-2/

