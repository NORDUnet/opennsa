Brocade
--------

**Config snippet:**

```
[brocade]
host=206.196.xx.xx
user=admin
fingerprint=63:3f:f5:68:e5:15:a1:6d:b0:61:40:2b:22:83:xx:xx
publickey=/home/opennsa/.ssh/id_rsa.pub
privatekey=/home/opennsa/.ssh/id_rsa
```



**Getting SSH keys in order:**

ssh-keygen generates the rsa/dsa key with a ID and a user in the public
key, for example:

```
---- BEGIN SSH2 PUBLIC KEY ----
key-dsa (... key ...) jab@home 
```

but Brocade doesn't understand the key with the index (key-dsa) and the
user (jab@home) on it so I had to remove them to make it work.

