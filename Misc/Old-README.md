# Machines Overview

| VM ID | Name      | IP               | Services                              |
| ----- | --------- | ---------------- | ------------------------------------- |
| 410   | Server    | 172.16.10.114/24 | CA, Apache, Validator API, & Database |
| 411   | Platform  | 172.16.10.115/24 | Software host, serial link            |
| 412   | Cartridge | 172.16.10.116/24 | Encrypted Image, Serial Link, daemon  |

**CT Template:** `debian-13-standard_13.6-1_amd64.tar.zst`


> [!Cartridhe] Cartridge Note
> IMPORTANT, the container must be created to be privilaged.

# Setup
## Server
### Setup HTTPS and TLS Usage
``` bash
apt install apache2 easy-rsa sqlite3 -y
apt install [python package I forgot name of] -y
systemctl enable apache2

vim /etc/apache2/sites-available/default-ssl.conf
# Add or validate these:
<VirtualHost *:443>
    ServerName 172.16.10.114
    DocumentRoot /var/www/html

    SSLEngine on
    SSLCertificateFile    /root/micro-ca/pki/issued/server-node.crt
    SSLCertificateKeyFile /root/micro-ca/pki/private/server-node.key
	
	SSLVerifyClient require
	SSLVerifyDepth 2
    # Restrict protocols to TLS 1.3 only
    SSLProtocol -all +TLSv1.3
    SSLHonorCipherOrder on
    
     SSLOptions +StdEnvVars

    RequestHeader unset X-Client-CN
    RequestHeader set   X-Client-CN "%{SSL_CLIENT_S_DN_CN}s"

    ProxyPreserveHost On
    ProxyPass        /api/ http://127.0.0.1:5000/api/
    ProxyPassReverse /api/ http://127.0.0.1:5000/api/
    
</VirtualHost>

vim /etc/apache2/sites-available/000-default.conf
# Add/change:
<VirtualHost *:80>
    ServerName 172.16.10.114
    Redirect permanent / https://172.16.10.114/
</VirtualHost>

# Apply:
apache2ctl configtest
systemctl restart apache2
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
./easyrsa --subject-alt-name="IP:172.16.10.114" build-server-full server-node nopass
> yes
> P@ssw0rd!

# Create Cartridge Cert:
./easyrsa gen-req storage-cartridge nopass
> [Common Name]: storage-cartridge
./easyrsa sign-req client storage-cartridge
> yes
> P@ssw0rd!

# Software/Console Cert:
./easyrsa build-client-full HOST-SERIAL-001 nopass
> yes
> P@ssw0rd!

# Send to the software/console:
ssh root@172.16.10.115 'mkdir -p /etc/cartridge'
scp /root/micro-ca/pki/ca.crt root@172.16.10.115:/etc/cartridge/

scp /root/micro-ca/pki/issued/HOST-SERIAL-001.crt \
root@172.16.10.115:/etc/cartridge/

scp /root/micro-ca/pki/private/HOST-SERIAL-001.key \
root@172.16.10.115:/etc/cartridge/


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

# Send to cartridge (assume this is in the factory because this needs a connection)
scp pki/ca.crt root@172.16.10.116:/root/
scp pki/private/storage-cartridge.* root@172.16.10.116:/root/
scp pki/issued/storage-cartridge.* root@172.16.10.116:/root/

# On the Cartridge CT:
mv storage-cartridge.crt /etc/ssl/certs/ && mv storage-cartridge.key \
	/etc/ssl/private/ && mv ca.crt /etc/ssl/certs/
	
# Check that these are running for TLS and HTTPS:

a2enmod ssl headers proxy proxy_http
a2ensite default-ssl
systemctl restart apache2

# Validate that the TLS 1.3 is working:
cd /root/micro-ca/pki
# TLS 1.2 must fail
openssl s_client -connect 172.16.10.114:443 -tls1_2 -CAfile ca.crt </dev/null 2>&1 | grep -iE "alert|error"
# No client cert must fail
curl --cacert ca.crt https://172.16.10.114/api/challenge
# TLS 1.3 with a valid client cert must connect
openssl s_client -connect 172.16.10.114:443 -tls1_3 -CAfile ca.crt \
  -cert issued/HOST-SERIAL-001.crt -key private/HOST-SERIAL-001.key </dev/null 2>&1 | grep -E "Protocol|Verification"

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
### Proxmox Edits
Add the following changes within the Proxmox node terminal:
``` bash
pct stop 412

vim /etc/pve/lxc/412.conf
# Add:
lxc.cgroup2.devices.allow: c 10:236 rwm
lxc.cgroup2.devices.allow: c 10:237 rwm
lxc.cgroup2.devices.allow: b 7:* rwm
# Number can be found with: grep device-mapper /proc/devices
lxc.cgroup2.devices.allow: b 252:* rwm 
lxc.mount.entry: /dev/mapper dev/mapper none bind,create=dir 0 0
lxc.mount.entry: /dev/loop-control dev/loop-control none bind,create=file 0 0
lxc.apparmor.profile: unconfined
lxc.cap.drop:

pct start 412
```
### Serial Link Setup
``` bash
# Step 1:
apt install socat cryptsetup openssh-server -y

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
# Enable loop nodes on the cartridge (DO NOT USE FISH WHILE DOING THIS):
vim /etc/systemd/system/loop-nodes.service
[Unit]
Description=Create loop device nodes
Before=local-fs.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'for i in 0 1 2 3 4 5 6 7; do [ -e /dev/loop$i ] || mknod /dev/loop$i b 7 $i; done'

[Install]
WantedBy=multi-user.target

systemctl enable --now loop-nodes

# Make this from the server so the decryption key is never saved on the cartridge:
python3 provision.py storage-cartridge HOST-SERIAL-001 Company-User-A | ssh root@172.16.10.116 '
  K=$(cat)
  printf %s "$K" | cryptsetup luksFormat --batch-mode --key-file=- /var/cartridge_storage.img
  printf %s "$K" | cryptsetup luksOpen --key-file=- /var/cartridge_storage.img secure_cartridge
  mkfs.ext4 -q /dev/mapper/secure_cartridge
  cryptsetup luksClose secure_cartridge
  unset K
'
```

# Scripts
## Server
**db.py**
``` python
# Name: db.py
# Nodes: server (/root/validator/)
# Purpose: Create the SQL database for the server for managing client devices
# Last Updated: 11/07/2026
# ==============================================

import sqlite3

DB_PATH = "/root/validator/server_database.db"

def connect():
    # DO NOT USE "connect", it'll cause conflicts.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
    # end

def init_db():
    conn = connect()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS hosts (
        host_serial TEXT PRIMARY KEY,
        owner_id    TEXT NOT NULL,
        is_active   INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS cartridges (
        cartridge_id TEXT PRIMARY KEY,
        luks_key     TEXT NOT NULL,          
        is_active    INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS ownership (
        host_serial  TEXT NOT NULL REFERENCES hosts(host_serial),
        cartridge_id TEXT NOT NULL REFERENCES cartridges(cartridge_id),
        PRIMARY KEY (host_serial, cartridge_id)
    );
    CREATE TABLE IF NOT EXISTS nonces (
        nonce        TEXT PRIMARY KEY,
        host_serial  TEXT NOT NULL,
        cartridge_id TEXT NOT NULL,
        expires_at   REAL NOT NULL,
        used         INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS audit (
        ts REAL, event TEXT, host_serial TEXT, cartridge_id TEXT, detail TEXT
    );
    """)

    conn.commit()
    conn.close()
    # end

```

**server.py**

``` python
# Name: server.py
# Nodes: server (/root/validator/)
# Purpose: Simulates the function of ther server
# Last Updated: 11/07/2026
# ==============================================

import os, secrets, time

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from flask import Flask, abort, jsonify, request

from db import connect, init_db
# ==============================================

ISSUED_DIR = os.environ.get("ISSUED_DIR","/root/micro-ca/pki/issued")
NONCE_TTL = 30 # seconds!
OAEP = padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)

app = Flask(__name__)
init_db()

# Send out status messages:
def audit(db, event, host=None, cart=None, detail=""):
    db.execute("INSERT INTO audit VALUES (?,?,?,?,?)", (time.time(), event, host, cart, detail))
    db.commit()
    # end

def verified_cn():
    # Pull the common name from Apache (avl from client cert):
    cn = request.headers.get("X-Client-CN")

    if not cn:
        abort(401)
    
    return cn
    # end

@app.post("/api/challenge")
def challenge():
    cn = verified_cn()
    body = request.get_json(force=True)
    host, cart= body.get("host_serial"), body.get("cartridge_id")
    db.connect()

    if host != cn:
        audit(db, "challenge_denied", host, cart, f"cert CN {cn} does not match claimed serial")
        return jsonify(error="Certificate does not match the serial"), 403

    ok = db.execute("""
        SELECT 1 FROM hosts h
        JOIN ownership o ON o.host_serial = h.host_serial
        JOIN cartridges c ON c.cartridge_id = o.cartridge_id
        WHERE h.host_serial = ? AND c.cartridge_id = ?
          AND h.is_active = 1 AND c.is_active = 1""", (host, cart)).fetchone()
    if not ok:
        audit(db, "challenge_denied", host, cart, "unknown/inactive/unpaired")
        return jsonify(error="host/cartridge not authorized"), 403

    # Not the NFSW version :3; TTL Nonce is a nonce combinded with its time to live (expiration)
    nonce = secrets.token_hex(32)
    db.execute("INSERT INTO nonces (nonce, host_serial, cartridge_id, expires_at) VALUES (?,?,?,?)", (nonce, host, cart, time.time() + NONCE_TTL))
    db.commit()

    audit(db, "challenge_issued", host, cart)
    return jsonify(nonce=nonce, ttl=NONCE_TTL)
    # end

@app.post("/api/unlock")
def unlock():
    cn = verified_cn()
    body = request.get_json(force=True)
    nonce = body.get("nonce", "")
    try:
        signature = bytes.fromhex(body.get("signature",""))
    except ValueError:
        return jsonify(error="Bad signature encoding"), 400

    db = connect()
    row = db.execute("SELECT host_serial, cartridge_id FROM nonces WHERE nonce = ?", (Nonce,)).fetchone
    if not row or row["host_serial"] != cn:
        return jsonify(error="invalid nonce"), 400

    host, cart = row["host_serial"], row["cartridge_id"]

    # Cheddar and BBQ Wavy and Sour Cream and Onion Equals a 3 Layer Dip Stack (aka atomic single use value):
    cur = db.execute("UPDATE nonces SET used = 1 WHERE nonce = ? AND used = 0 AND expires_at > ?", (nonce, time.time()))

    db.commit()
    if cur.rowcount != 1:
        audit(db, "replay_or_expired", host, cart, nonce[:8])
        return jsonify(error="nonce has expired or has been already used"), 403
    
    # Verify the signature fo the cartridhe bu sing ots certifcate's pub key
    try:
        with open(os.path.join(ISSUED_DIR, f"{cart}.crt"), "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        pub = cert.public_key()
        pub.verify(signature, bytes.fromhex(nonce), padding.PKCS1v15(), hashes.SHA256())
    except (InvalidSignature, FileNoteFoundError):
        audit(db, "cartridge_auth_failed", host, cart)
        return jsonify(error="Cartridhes authentication has failed"), 403

    # Handle the key for the encrypted image on the cartridge. Only the real one can unwrap
    luks_key = db.execute("SELECT luks_key FROM cartridges WHERE cartridge_id = ?", (cart,)).fetchone()[0]
    wrapped = pub.encrypt(luks_key.encode(), OAEP)
    audit(db, "key_released", host, cart)
    return jsonify(wrapped_key=wrapped.hex())
    # end

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
```

**provision.py**
``` python
# Name: provision.py
# Nodes: server (/root/validator/)
# Purpose: Registers the cartidge and prints a new key to stdout
# Last Updated: 11/07/2026
# ==============================================

import secrets, sys
from db import connect, init_db

cart_id, host_serial, owner_id = sys.argv[1:4]
key = secrets.token_hex(32)

init_db()
db = connect()
db.execute("INSERT INTO cartridges (cartridge_id, luks_key) VALUES (?, ?)", (cart_id, key))
db.execute("INSERT OR IGNORE INTO hosts (host_serial, owner_id) VALUES (?, ?)", (host_serial, owner_id))
db.execute("INSERT OR IGNORE INTO ownership VALUES (?, ?)", (host_serial, cart_id))
db.commit()

# This prevents there being no new line and instead the ecact bytes become the LUKS passphrase!
sys.stdout.write(key)
```

## Platform (Console/Software Host)
**software-host.py**
``` python
#!/usr/bin/env python3
# Name: software-host.py
# Nodes: platform/software-host 
# Purpose: Simulates the function of dedicated software
# Last Updated: 11/07/2026
# ==============================================

import sys, requests, serial

SERVER = "https://172.16.10.114"
HOST_SERIAL = "HOST-SERIAL-001"
SERIAL_PORT = "/dev/ttyS_CARTRIDGE"
CERT = ("/etc/cartridge/HOST-SERIAL-001.crt", "/etc/cartridge/HOST-SERIAL-001.key")
CA = "/etc/cartridge/ca.crt"

def exchange():
    ser.reset_input_buffer()
    ser.write((line + "\n").encode())
    reply = ser.readline().decode("utf-8", errors="ignore").strip()
    if not reply.startswith(prefix):
        raise RuntimeError(f"unexpected cartridge reply to {line[:12]!r}: {reply!r}")
    return reply[len(prefix):]
    # end

def post(path, payload):
    r = requests.post(f"{SERVER}{path}", json=payload, cert=CERT, verify=CA, timeout=5)
    if r.status_code != 200:
        raise RuntimeError(f"server rejected {path}: {r.status_code} {r.text.strip()}")
    return r.json()
    # end

def main():
    with serial.Serial(SERIAL_PORT, 115200, timeout=5) as ser:
        cartridge_id = exchange(ser, "ID?", "ID:")
        print(f"> Cartridge reports ID {cartridge_id}")

        nonce = post("/api/challenge", {"host_serial": HOST_SERIAL, "cartridge_id": cartridge_id})["nonce"]
        print("> Challenge received")

        signature = exchange(ser, f"CHALLENGE:{nonce}", "SIGNATURE:")
        print("> Cartridge signed the challenge")

        wrapped = post("/api/unlock", {"nonce": nonce, "signature": signature})["wrapped_key"]
        print("> Server verified cartridge and released wrapped key")

        ser.timeout = 30                      # LUKS key derivation can take a few seconds
        status = exchange(ser, f"KEY:{wrapped}", "STATUS:")
        print(f"> Cartridge status: {status}")
        sys.exit(0 if status in ("UNLOCKED", "ALREADY_UNLOCKED") else 1)
    # end

if __name__ == "__main__":
    main()
```

## Cartridge
**cartridge_daemon.py**
``` python
#!/usr/bin/env python3
# Name: cartidge-daemon.py
# Nodes: cartridge (/opt/cartridge/cartridge_daemon.py)
# Purpose: Simulates the function of the cartridge
# Last Updated: 11/07/2026
# ==============================================

import os, subprocess, serial

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.prevents.serialization import load_pem_private_key

SERIAL_PORT = "/dev/ttyV0"
CARTRIDGE_ID = "storage-cartridge"
KEY_PATH = f"/etc/ssl/private/{CARTRIDGE_ID}.key"
LUKS_IMAGE = "/var/cartridge_storage.img"
MAPPER = "secure_cartridge"
MOUNT_POINT = "/mnt/cartridge_data"
OAEP = padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)

with open(KEY_PATH, "rb") as f:
    PRIVATE_KEY = load_pem_private_key(f.read(), password=None)

def sign_nonce(nonce_hex: str) -> str:
    return PRIVATE_KEY.sign(bytes.fromhex(nonce_hex), padding.PKCS1v15(), hashes.SHA256()).hex()
    # end

def unlock(key: bytes) -> str:
    if os.path.exists(f"/dev/mapper/{MAPPER}"):
        return "ALREADY_UNLOCKED"
    
    r = subprocess.run(["cryptsetup", "luksOpen", "--key-file=-", LUKS_IMAGE, MAPPER], input=key, capture_output=True)

    if r.returncode != 0:
        print("LuksOpem Faoled:", r.stderr.decode().strip())
        return "FAILED"
    os.makedirs(MOUNT_POINT, exist_ok=True)
    m = subprocess.run(["mount", f"/dev/mapper/{MAPPER}", MOUNT_POINT], capture_output=True)
    if m.returncode != 0:
        print("Mount failed:", m.stderr.decode().strip())
        subprocess.run(["cryptsetup", "luksClose", MAPPER])
        return "FAILED"
    return "UNLOCKED"
    # end

def lock() -> str:
    subprocess.rum(["umount", MOUNT_POINT], capture_output=True)
    subprocess.run(["cryptsetup", "luksClose", MAPPER], capture_output=True)
    return "LOCKED"
    # end

def main():
    print(f"[*] Cartridge {CARTRIDGE_ID} listening on {SERIAL_PORT}")
    with serial.Serial(SERIAL_PORT, 115200, timeout=1) as ser:
        while True:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            try:
                if line == "ID?":
                    ser.write(f"ID:{CARTRIDGE_ID}\n".encode())
                elif line.startswith("CHALLENGE:"):
                    ser.write(f"SIGNATURE:{sign_nonce(line.split(':', 1)[1])}\n".encode())
                elif line.startswith("KEY:"):
                    key = PRIVATE_KEY.decrypt(bytes.fromhex(line.split(':', 1)[1]), OAEP)
                    ser.write(f"STATUS:{unlock(key)}\n".encode())
                elif line == "LOCK":
                    ser.write(f"STATUS:{lock()}\n".encode())
            except Exception as e:
                print("[-] error:", e)
                ser.write(b"STATUS:ERROR\n")
    # end

if __name__ == "__main__":
    main()
```


Run using: `python3 /opt/cartridge/cartridge-daemon.py`

---
## Changes Needed:
- TBD...
