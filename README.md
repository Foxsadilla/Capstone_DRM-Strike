## Step 1. Proxmox: let CT 412 use device-mapper and loop devices

**[PVE]**

```bash
modprobe dm_mod dm_crypt loop
grep device-mapper /proc/devices      # note the number, e.g. 252
ls -l /dev/mapper/control /dev/loop-control   # expect c 10,236 and c 10,237
pct stop 412
nano /etc/pve/lxc/412.conf
```

Append (replace `252` with the number you found, unless its still the same):

```
lxc.cgroup2.devices.allow: c 10:236 rwm
lxc.cgroup2.devices.allow: c 10:237 rwm
lxc.cgroup2.devices.allow: b 7:* rwm
lxc.cgroup2.devices.allow: b 252:* rwm
lxc.mount.entry: /dev/mapper dev/mapper none bind,create=dir 0 0
lxc.mount.entry: /dev/loop-control dev/loop-control none bind,create=file 0 0
lxc.apparmor.profile: unconfined
lxc.cap.drop:
```

```bash
pct start 412
```

The container must be **privileged**.

---

## Step 2. Install packages

**[S]**

```bash
apt update && apt install -y apache2 easy-rsa sqlite3 python3-flask python3-cryptography
```

**[P]**

```bash
apt update && apt install -y socat python3-requests python3-serial
```

**[C]**

```bash
apt update && apt install -y socat cryptsetup openssh-server python3-serial python3-cryptography
```

Optional but convenient: password-less SSH from the server, so the provisioning pipe doesn't stop at a password prompt.

**[S]**

```bash
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
ssh-copy-id root@172.16.10.115
ssh-copy-id root@172.16.10.116
```

---

## Step 3. Micro-CA and certificates

**[S]**. Skip this step if `/root/micro-ca/pki/ca.crt` already exists. **Never re-run `init-pki` on an existing CA**; it destroys it.

```bash
make-cadir /root/micro-ca && cd /root/micro-ca
export EASYRSA_ALGO=rsa                      # the code uses RSA signatures and RSA-OAEP
./easyrsa init-pki
./easyrsa build-ca                           # set a CA passphrase; Common Name: 172.16.10.114
./easyrsa --subject-alt-name="IP:172.16.10.114" build-server-full server-node nopass
./easyrsa build-client-full storage-cartridge nopass     # cartridge ID = this CN
./easyrsa build-client-full HOST-SERIAL-001 nopass       # host serial = this CN
```

Signing commands ask for the **CA passphrase** (answer `yes` if asked to confirm).

**Verify:**

```bash
cd /root/micro-ca
openssl x509 -in pki/issued/server-node.crt -noout -text | grep -E "Public Key Algorithm|IP Address"
openssl x509 -in pki/issued/storage-cartridge.crt -noout -text | grep "Public Key Algorithm"
```

Expect `rsaEncryption` on both and `IP Address:172.16.10.114` on the server cert. If you see `id-ecPublicKey`, reissue with `EASYRSA_ALGO=rsa` set. If the IP is missing, Python `requests` will reject the server.

---

## Step 4. Distribute certificates

**[S]**

```bash
cd /root/micro-ca

# Platform (software host)
ssh root@172.16.10.115 'mkdir -p /etc/cartridge'
scp pki/ca.crt pki/issued/HOST-SERIAL-001.crt pki/private/HOST-SERIAL-001.key root@172.16.10.115:/etc/cartridge/
ssh root@172.16.10.115 'chmod 600 /etc/cartridge/HOST-SERIAL-001.key'

# Cartridge ("factory" step; the cartridge only needs its private key and the CA cert)
scp pki/ca.crt pki/private/storage-cartridge.key root@172.16.10.116:/root/
ssh root@172.16.10.116 'mv /root/ca.crt /etc/ssl/certs/ && mv /root/storage-cartridge.key /etc/ssl/private/ && chmod 600 /etc/ssl/private/storage-cartridge.key'
```

---

## Step 5. Apache: TLS 1.3, mTLS, reverse proxy

**[S]**

```bash
nano /etc/apache2/sites-available/default-ssl.conf
```

Make the whole file just this:

```apache
<VirtualHost *:443>
    ServerName 172.16.10.114
    DocumentRoot /var/www/html

    SSLEngine on
    SSLCertificateFile    /root/micro-ca/pki/issued/server-node.crt
    SSLCertificateKeyFile /root/micro-ca/pki/private/server-node.key
    SSLCACertificateFile  /root/micro-ca/pki/ca.crt
    SSLVerifyClient require
    SSLVerifyDepth 2
    SSLProtocol -all +TLSv1.3

    SSLOptions +StdEnvVars
    RequestHeader unset X-Client-CN
    RequestHeader set   X-Client-CN "%{SSL_CLIENT_S_DN_CN}s"

    ProxyPreserveHost On
    ProxyPass        /api/ http://127.0.0.1:5000/api/
    ProxyPassReverse /api/ http://127.0.0.1:5000/api/
</VirtualHost>
```

```bash
nano /etc/apache2/sites-available/000-default.conf
```

```apache
<VirtualHost *:80>
    ServerName 172.16.10.114
    Redirect permanent / https://172.16.10.114/
</VirtualHost>
```

Enable modules **then** restart:

```bash
a2enmod ssl headers proxy proxy_http
a2ensite default-ssl
apache2ctl configtest          # expect: Syntax OK
systemctl enable apache2 && systemctl restart apache2
```

**Verify TLS:**

```bash
cd /root/micro-ca/pki
openssl s_client -connect 172.16.10.114:443 -tls1_2 -CAfile ca.crt </dev/null 2>&1 | grep -iE "alert|error"      # must fail
curl --cacert ca.crt https://172.16.10.114/api/challenge                                                          # must fail (no client cert)
openssl s_client -connect 172.16.10.114:443 -tls1_3 -CAfile ca.crt \
  -cert issued/HOST-SERIAL-001.crt -key private/HOST-SERIAL-001.key </dev/null 2>&1 | grep -E "Protocol|Verification"   # TLSv1.3, Verification: OK
```

---

## Step 6. Cartridge: loop nodes and the encrypted image

**[C]**

```bash
cat > /etc/systemd/system/loop-nodes.service <<'EOF'
[Unit]
Description=Create loop device nodes
Before=local-fs.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'for i in 0 1 2 3 4 5 6 7; do [ -e /dev/loop$i ] || mknod /dev/loop$i b 7 $i; done'

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now loop-nodes

ls -l /dev/loop[0-7] /dev/loop-control
# must print /dev/loop0 with no "(lost)":
losetup -f                  
truncate -s 512M /var/cartridge_storage.img
```

Optional sanity test that cryptsetup works in the container:

```bash
dd if=/dev/zero of=/tmp/t.img bs=1M count=32
echo test | cryptsetup luksFormat --batch-mode --key-file=- /tmp/t.img && echo OK
rm -f /tmp/t.img
```

---

## Step 7. Validator files and provisioning

**[S]**

```bash
mkdir -p /root/validator && cd /root/validator
# Create db.py, server.py and provision.py
python3 -m py_compile db.py server.py provision.py && echo "syntax OK"
# always start provisioning from a clean database:
rm -f server_database.db                     
```

Provision. This registers the cartridge, generates the key, and pipes it straight into `cryptsetup` on the cartridge:

```bash
python3 provision.py storage-cartridge HOST-SERIAL-001 Company-User-A | ssh root@172.16.10.116 '
  K=$(cat)
  printf %s "$K" | cryptsetup luksFormat --batch-mode --key-file=- /var/cartridge_storage.img
  printf %s "$K" | cryptsetup luksOpen --key-file=- /var/cartridge_storage.img secure_cartridge
  mkfs.ext4 -q /dev/mapper/secure_cartridge
  cryptsetup luksClose secure_cartridge
  unset K
'
echo "exit codes: ${PIPESTATUS[*]}"          # expect: 0 0
chmod 600 server_database.db                 # it holds the keys in the clear
```

**Verify:**

```bash
sqlite3 server_database.db "SELECT cartridge_id, length(luks_key) FROM cartridges; SELECT * FROM ownership;"
ssh root@172.16.10.116 'cryptsetup isLuks /var/cartridge_storage.img && echo LUKS; ls /dev/mapper'
```

Expect `storage-cartridge|64`, the ownership row, `LUKS`, and **no** `secure_cartridge` in `/dev/mapper` (it is closed).

> If a run fails part-way, the database already holds a key the image doesn't. Delete `server_database.db` and run the whole step again.

---

## Step 8. Serial link

**[C]**, own terminal (leave running):

```bash
socat -d -d PTY,link=/dev/ttyV0,raw,echo=0 TCP-LISTEN:4000,reuseaddr,fork
```

**[P]**, own terminal (leave running):

```bash
socat -d -d PTY,link=/dev/ttyS_CARTRIDGE,raw,echo=0 TCP:172.16.10.116:4000
```

**Test:**

```bash
# [C] second shell
cat < /dev/ttyV0
# [P] second shell
echo TEST_CARTRIDGE_LINK > /dev/ttyS_CARTRIDGE
```

The text should appear on [C]. Press Ctrl+C to stop the `cat` before starting the daemon.

---

## Step 9. Start the API and the daemon

**[S]**, own terminal:

```bash
cd /root/validator && python3 server.py
```

Expect `Running on http://127.0.0.1:5000`.

**[P]**, check the whole TLS → Apache → Flask chain:

```bash
cd /etc/cartridge
curl -s -o /dev/null -w "%{http_code}\n" --cacert ca.crt --cert HOST-SERIAL-001.crt --key HOST-SERIAL-001.key https://172.16.10.114/api/challenge
```

`405` is the **good** answer here: the route only accepts POST, so Flask was reached. `503` means Flask isn't running; `401` means the `X-Client-CN` header is missing.

**[C]**, install and start the daemon, own terminal:

```bash
mkdir -p /opt/cartridge
# Create /opt/cartridge/cartridge_daemon.py
python3 /opt/cartridge/cartridge_daemon.py
```

Expect `[*] Cartridge storage-cartridge listening on /dev/ttyV0`.

---

## Step 10. Unlock the cartridge

**[P]**

```bash
python3 software-host.py; echo "exit code: $?"
```

Expected:

```
> Cartridge reports ID storage-cartridge
> Challenge received
> Cartridge signed the challenge
> Server verified cartridge and released wrapped key
> Cartridge status: UNLOCKED
exit code: 0
```

**[C]** (check from a spare shell):

```bash
mount | grep cartridge_data
echo "hello from the cartridge" > /mnt/cartridge_data/test.txt
```

**Lock it again**, from **[P]**:

```bash
python3 -c "import serial; s=serial.Serial('/dev/ttyS_CARTRIDGE',115200,timeout=5); s.write(b'LOCK\n'); print(s.readline().decode().strip())"
```

Expect `STATUS:LOCKED`. On **[C]**, confirm the data is unreadable at rest and the mount is gone:

```bash
mount | grep cartridge_data || echo "not mounted"
grep -a -c "hello from the cartridge" /var/cartridge_storage.img     # expect 0
```

Run `software-host.py` again to unlock; `cat /mnt/cartridge_data/test.txt` still shows the file.

**Audit log**, on **[S]**:

```bash
sqlite3 /root/validator/server_database.db \
  "SELECT datetime(ts,'unixepoch','localtime'), event, host_serial, cartridge_id FROM audit ORDER BY ts DESC LIMIT 10;"
```

---

## Step 11. Security tests

All from **[P]**, in `/etc/cartridge`. Define a helper first:

```bash
cd /etc/cartridge
c() { curl -s --cacert ca.crt --cert HOST-SERIAL-001.crt --key HOST-SERIAL-001.key "$@"; }
```

**Replay and single-use nonce**

```bash
N=$(c -d '{"host_serial":"HOST-SERIAL-001","cartridge_id":"storage-cartridge"}' \
    https://172.16.10.114/api/challenge | python3 -c 'import sys,json; print(json.load(sys.stdin)["nonce"])')
for i in 1 2; do c -d "{\"nonce\":\"$N\",\"signature\":\"00\"}" https://172.16.10.114/api/unlock; echo; done
```

1st call: `403 ... authentication has failed` (nonce is consumed even though the signature is bad). 2nd call: `403 ... already been used`.

**Expired nonce**: repeat the `N=` line, `sleep 35`, then call `/api/unlock`. Expect the same "expired or used" error.

**Spoofed serial** (valid cert, wrong claimed identity)

```bash
c -d '{"host_serial":"HOST-SERIAL-002","cartridge_id":"storage-cartridge"}' https://172.16.10.114/api/challenge
```

Expect `403 Certificate does not match the serial`.

**Revoked host**, on **[S]**:

```bash
sqlite3 /root/validator/server_database.db "UPDATE hosts SET is_active=0 WHERE host_serial='HOST-SERIAL-001';"
```

Run `software-host.py` on [P]: it fails with `server rejected /api/challenge: 403`. Restore with `is_active=1`.

---

## Reset and re-run

```bash
# [C]  lock and close everything
umount /mnt/cartridge_data 2>/dev/null; cryptsetup luksClose secure_cartridge 2>/dev/null
# [S]  wipe registrations
rm -f /root/validator/server_database.db
# then repeat Step 7 (provision) and restart the API (Step 9)
```

## Troubleshooting

|Symptom|Cause / fix|
|---|---|
|`Cannot initialize device-mapper`|`dm_mod` not loaded on the host, or CT 412 not privileged / missing mount entry (Step 1)|
|`Attaching loopback device failed`|No `/dev/loopN` nodes in the container (Step 6)|
|`mkfs.ext4: Operation not permitted`|Wrong device-mapper major in `412.conf`; restart the container fully|
|`UNIQUE constraint failed: cartridges.cartridge_id`|Stale registration; delete `server_database.db` and re-provision|
|`ModuleNotFoundError: serial`|`apt install python3-serial` on that machine|
|`SSLError ... doesn't match` / IP mismatch|Server cert has no `IP:172.16.10.114` SAN (Step 3)|
|`curl` returns `503`|Flask isn't running on `127.0.0.1:5000`|
|`403 Certificate does not match the serial`|Host cert CN isn't `HOST-SERIAL-001`|
|Cartridge status `FAILED`|Key in the database doesn't match the image; reset and re-provision. The daemon prints the `cryptsetup` error.|
|Host script hangs on serial|Both `socat` processes and the daemon must be running (Step 8, 9)|
|`could not open port /dev/ttyS_CARTRIDGE`|`socat` on [P] isn't running|


---
# Code
## Server
![[server.py]]
![[provision.py]]
![[db.py]]
## Platform
![[software-host.py]]
## Cartridge
![[cartridge-daemon.py]]