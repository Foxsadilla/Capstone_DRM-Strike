# Machines Overview

| VM ID | Name      | IP               |
| ----- | --------- | ---------------- |
| 410   | Server    | 172.16.10.114/24 |
| 411   | Platform  | 172.16.10.115/24 |
| 412   | Cartridge | 172.16.10.116/24 |
**CT Template:** `debian-13-standard_13.6-1_amd64.tar.zst`

# Setup
## Server
### Setup HTTPS and TLS Usage
``` bash
apt install apache2 -y
systemctl enable apache2

# Set to use HTTPS:
# Generate self-signed cert:
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/apache-selfsigned.key \
  -out /etc/ssl/certs/apache-selfsigned.crt
> [Common Name]: 172.16.10.114

vim /etc/apache2/sites-available/default-ssl.conf
# Add or validate these:
<VirtualHost *:443>
    ServerName 172.16.10.114
    DocumentRoot /var/www/html

    SSLEngine on
    SSLCertificateFile /etc/ssl/certs/ssl-cert-snakeoil.pem
    SSLCertificateKeyFile /etc/ssl/private/ssl-cert-snakeoil.key

    # Restrict protocols to TLS 1.3 only
    SSLProtocol -all +TLSv1.3
    SSLHonorCipherOrder on
</VirtualHost>

vim /etc/apache2/sites-available/000-default.conf
# Add:
ServerName 172.16.10.114
RewriteEngine On
RewriteCond %{HTTPS} off
RewriteRule ^(.*)$ https://%{HTTP_HOST}$1 [R=301,L]
```
### Setup Micro-CA
``` bash
# initliaze the PKI micro CA Env:
apt install easy-rsa -y
make-cadir ~/micro-ca
cd ~/micro-ca 
./easyrsa init-pki
./easyrsa build-ca
> [Passphrase]: P@ssw0rd!
> [Common Name]: 172.16.10.114

# Create Server Cert:
./easyrsa gen-req server-node nopass
> [Common Name]: 172.16.10.114
./easyrsa sign-req server server-node
> yes
> P@ssw0rd!

# Create Cartridge Cert:
./easyrsa gen-req storage-cartridge nopass
> [Common Name]: storage-cartridge
./easyrsa sign-req client storage-cartridge
> yes
> P@ssw0rd!

# Software/Console Cert:
./easyrsa gen-req consumer-software nopass
> 172.16.10.115
./easyrsa sign-req client consumer-software
> yes
> P@ssw0rd!

# Force Apache to use mTLS w/ TLS 1.3
vim /etc/apache2/sites-available/default-ssl.conf
# Add and change:
    # Server Cert and Key
    SSLCertificateFile /root/micro-ca/pki/issued/server-node.crt
    SSLCertificateKeyFile /root/micro-ca/pki/private/server-node.key
    # Micro-CA Root Cert for Client Verification
    SSLCACertificateFile /root/micro-ca/pki/ca.crt
    # Force mTLS, Require and verify client certs
    SSLVerifyClient require
    SSLVerifyDepth 2

# Validate:
apache2ctl configtest
systemctl restart apache2

# Simulate that the cartridge does not have a network connection scp the files to it :)
scp pki/ca.crt root@172.16.10.116:/root/
scp pki/private/storage-cartridge.* root@172.16.10.116:/root/
scp pki/issued/storage-cartridge.* root@172.16.10.116:/root/

# On the Cartridge CT:
mv storage-cartridge.crt /etc/ssl/certs/ && mv storage-cartridge.key \
	/etc/ssl/private/ && mv ca.crt /etc/ssl/certs/

```


## Platform (Console)
### Serial Link Setup
``` bash
# Going to number these so its easier to jump between the sections :P
# Step 1:
apt install socat -y

# Step 2: Go to cartirdge Step 2

# Step 3: Expose to the cartidge's serial link by mapping it to a local port
# Keep this in it's own window:
socat -d -d PTY,link=/dev/ttyS_CARTRIDGE,raw,echo=0 TCP:172.16.10.116:4000
# Check that it is mounted in new window:
ls -l /dev/ttyS_CARTRIDGE

# Step 4: Test that communications can be sent (Use the altered command on Cartridge Step 3)
# While step 3 runs, in a new window run:
echo "TEST_CARTRIDGE_LINK" > /dev/ttyS_CARTRIDGE

```

## Cartridge
### Serial Link Setup
``` bash
# Step 1:
apt install socat -y

# Step 2: Create a binded virtual psuedoterminanl and expose over a TCP port (4000):
# /dev/ttyV0 is a virtual serial device that a local service can RW with
socat -d -d PTY,link=/dev/ttyV0,raw,echo=0 TCP-LISTEN:4000,reuseaddr,fork

# Step 3: Test connectivity
# End current session on both CTs and start it again but use this instead on the cartidge:
socat -d -d PTY,link=/dev/ttyV0,raw,echo=0 TCP-LISTEN:4000,reuseaddr,fork &
# Check output from Platform Step 4 test:
cat </dev/ttyV0
```

### Encryption at Rest 
``` bash
apt install cryptsetup -y

# Create a raw image file to emualte data being stored
dd if=/dev/zero of=/var/cartridge_storage.img bs=1M count=512

# Encrypt it:
cryptsetup luksFormat /var/cartridge_storage.img
> YES
> P@ssw0rd!
> P@ssw0rd!
```

# Scripts
## Server
**server-db.py**
``` python
```

**server.py**
``` python
```

**provision.py**
``` python
```

## Platform (Console/Software Host)

## Cartridge

---
## Changes Needed:
1. **Reissue the server cert with an IP SAN.** Yours has `172.16.10.114` only as the CN. Python `requests` ignores the CN and will reject the cert. Check first with `openssl x509 -in /root/micro-ca/pki/issued/server-node.crt -noout -text | grep -A1 "Alternative"`. If no `IP Address:172.16.10.114` appears, delete the old `server-node` req, key and crt from the `pki` folder. Then rerun `./easyrsa --subject-alt-name="IP:172.16.10.114" build-server-full server-node nopass`. Your Apache paths don’t change.
2. **Add the proxy and identity header to `default-ssl.conf`.** Add the `SSLOptions`, `RequestHeader` and `ProxyPass` lines from section 4 of the runbook. Also run `a2enmod headers proxy proxy_http`. Everything else in your vhost stays.
3. **Redo the LUKS passphrase.** Right now the volume uses `P@ssw0rd!`, and the whole design depends on the server holding a generated key. The image is empty, so run the section 6.2 pipeline (`provision.py ... | ssh root@172.16.10.116 '...'`). It reformats the image with the server’s key and builds the filesystem. 