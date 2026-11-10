# Runbook: Server-Validated Encrypted Cartridge (mTLS + Anti-Replay + LUKS)

## 1. What this builds

A company-owned **server** gates access to a company-owned **storage cartridge**. The consumer's **software host** can only read the cartridge after the server has verified (a) the host's identity and (b) that the cartridge is the genuine, registered one.

|Component|Proxmox CT|Role|Address|
|---|---|---|---|
|Server|410|Micro-CA, Apache TLS 1.3 + mTLS front end, Flask validation API, SQLite database|`172.16.10.114`|
|Software host (Platform)|411|Holds a client certificate, talks to the server over the network and to the cartridge over serial|`172.16.10.115`|
|Cartridge|412|Container with a LUKS-encrypted image; no internet in production; reachable only over a simulated serial link|`172.16.10.116`|

All three are `debian-13-standard_13.6-1_amd64.tar.zst` containers and the commands below run as `root`. The cartridge is addressed by its certificate CN, **`storage-cartridge`**, which is also its cartridge ID in the database.

**Design decisions** (these replace several inconsistent steps from the original chat):

1. **Apache terminates TLS 1.3 + mTLS and reverse-proxies to Flask on `127.0.0.1:5000`.** The original had both Apache and Flask binding port 443, which cannot work.
2. **The host's identity is the CN of its client certificate** (e.g. `HOST-SERIAL-001`). Apache passes the verified CN to Flask in a header, and Flask checks it against the request body. A serial number alone is never trusted.
3. **The server verifies the cartridge's signature for real** (the original left it as a stub) using the public key in the cartridge's certificate.
4. **The LUKS key is wrapped (RSA-OAEP) to the cartridge's public key** before leaving the server. The host relays ciphertext it cannot read.
5. **The LUKS key is generated on the server at provisioning time** and piped straight into `cryptsetup` on the cartridge. It never exists as a file on the cartridge.
6. **Nonces are single-use, short-lived, and bound to one host and one cartridge**, and are consumed atomically.

### Protocol

```
Host                         Cartridge (serial)                Server (mTLS)
 |-- ID? -------------------->|                                    |
 |<-- ID:storage-cartridge ---|                                    |
 |-- POST /api/challenge {host_serial, cartridge_id} ------------->|  checks host, cartridge, ownership
 |<-- {nonce} ------------------------------------------------------|  stores nonce (30 s, unused)
 |-- CHALLENGE:<nonce> ------>|                                    |
 |<-- SIGNATURE:<sig> --------|                                    |
 |-- POST /api/unlock {nonce, signature} -------------------------->|  consumes nonce, verifies signature
 |<-- {wrapped_key} ------------------------------------------------|  key wrapped to cartridge pubkey
 |-- KEY:<wrapped_key> ------>|  unwrap, luksOpen, mount           |
 |<-- STATUS:UNLOCKED --------|                                    |
```

### Starting from an existing lab (what is already done vs. what changes)

If you have already followed the earlier README, **do not roll the containers back**. Use this table to skip or redo steps. Optionally snapshot first so any step is cheap to undo: `pct snapshot 410 pre-runbook` (same for 411 and 412).

|Item from the earlier README|Status|Where handled|
|---|---|---|
|Containers, IPs, Apache installed, port 80 → 443 redirect|**Keep**|Section 4 (redirect is replaced by a simpler `Redirect`)|
|TLS 1.3 only (`SSLProtocol -all +TLSv1.3`) and `SSLVerifyClient require`|**Keep**|Section 4|
|Micro-CA (`/root/micro-ca`, passphrase-protected)|**Keep. Do not re-run `init-pki`/`build-ca`**|Section 3|
|`storage-cartridge` cert and key, copied to the cartridge|**Keep**|Section 6.1|
|Server cert (CN only, no IP SAN)|**Redo**: Python `requests` ignores the CN and rejects it|Section 3.1|
|Host cert `consumer-software` (CN = `172.16.10.115`)|**Replace** with a serial-style CN, `HOST-SERIAL-001`|Section 3.2|
|Apache vhost|**Add** header + reverse-proxy lines, `a2enmod headers proxy proxy_http`|Section 4|
|`socat` serial link (`/dev/ttyV0` ↔ `/dev/ttyS_CARTRIDGE`)|**Keep** (already tested)|Section 7|
|LUKS image formatted with passphrase `P@ssw0rd!`|**Redo** with the server-generated key; the image is empty, so nothing is lost|Section 6.2|
|"Create Daemon" (unfinished)|**New**|Sections 5, 8, 9|

---

## 2. Prerequisites

On **all three** machines (Debian/Ubuntu):

```bash
apt update
apt install -y python3-flask python3-requests python3-cryptography python3-serial socat
```

Additionally:

- **Server:** `apt install -y apache2 easy-rsa sqlite3`
- **Cartridge:** `apt install -y cryptsetup openssh-server`. A container needs enough privilege for device-mapper (`--privileged`, or `CAP_SYS_ADMIN` plus `/dev/mapper` and `/dev/loop-control`), or `cryptsetup` will fail.

> Use `apt` packages rather than `pip`. Recent Debian releases block system-wide `pip install` (PEP 668).

> **Check the terminal.** Several problems in the original session came from running commands on the wrong machine (e.g. `/etc/apache2` "missing" on the cartridge). Each section below states where to run it.

---

## 3. Micro-CA and certificates (run on the Server)

The CA already exists at `/root/micro-ca` and is passphrase-protected. **Do not re-run `init-pki` or `build-ca`**: that would destroy it and invalidate every certificate. (On a brand-new lab you would run `make-cadir /root/micro-ca`, `./easyrsa init-pki`, then `./easyrsa build-ca` and set a CA passphrase.)

```bash
cd /root/micro-ca
```

Every command below that signs a certificate prompts for the **CA passphrase**, so none of them use `--batch`. The `nopass` flag only affects the new certificate's own private key.

The **client CNs matter**: they are the serial/ID values the server enforces.

### 3.1 Server certificate with an IP SAN

Clients connect by IP, and Python `requests` validates the IP against the certificate's Subject Alternative Name, not the CN. Check what you have:

```bash
openssl x509 -in pki/issued/server-node.crt -noout -text | grep -A1 "Alternative"
```

If `IP Address:172.16.10.114` is **not** listed, reissue it:

```bash
rm -f pki/reqs/server-node.req pki/private/server-node.key pki/issued/server-node.crt
./easyrsa --subject-alt-name="IP:172.16.10.114" build-server-full server-node nopass
```

The paths in your Apache vhost (`/root/micro-ca/pki/issued/server-node.crt` and `.../private/server-node.key`) stay the same. If Easy-RSA refuses because the name was already issued, run `./easyrsa revoke server-node` first, then repeat.

### 3.2 Cartridge and host identities

```bash
# Cartridge identity (CN = cartridge ID). Already issued in the earlier README: skip if
# pki/issued/storage-cartridge.crt exists.
./easyrsa build-client-full storage-cartridge nopass

# Software host identity (CN = host serial). Replaces the old consumer-software cert,
# whose CN was just the host's IP address.
./easyrsa build-client-full HOST-SERIAL-001 nopass
```

Results live in `/root/micro-ca/pki/`: `ca.crt`, `issued/*.crt`, `private/*.key`. Apache reads the server cert and CA directly from there at startup (it starts as root), so nothing needs to be copied.

---

## 4. Apache: TLS 1.3 only, HTTPS only, mTLS required (run on the Server)

```bash
a2enmod ssl headers proxy proxy_http
a2ensite default-ssl
```

**`/etc/apache2/sites-available/default-ssl.conf`**

Your existing vhost already has the server cert, CA, `SSLVerifyClient require` and TLS 1.3 settings. The new parts are `SSLOptions`, the two `RequestHeader` lines and the `Proxy*` lines. `DocumentRoot` and `SSLHonorCipherOrder` are no longer needed (cipher order does not apply to TLS 1.3), and any leftover snakeoil certificate lines must be gone.

```apache
<VirtualHost *:443>
    ServerName 172.16.10.114

    SSLEngine on
    SSLCertificateFile    /root/micro-ca/pki/issued/server-node.crt
    SSLCertificateKeyFile /root/micro-ca/pki/private/server-node.key

    # Only clients with a certificate signed by our micro-CA may connect
    SSLCACertificateFile  /root/micro-ca/pki/ca.crt
    SSLVerifyClient require
    SSLVerifyDepth 1

    # TLS 1.3 only
    SSLProtocol -all +TLSv1.3

    SSLOptions +StdEnvVars

    # Pass the verified certificate CN to the app. Strip any client-supplied copy first.
    RequestHeader unset X-Client-CN
    RequestHeader set   X-Client-CN "%{SSL_CLIENT_S_DN_CN}s"

    ProxyPreserveHost On
    ProxyPass        /api/ http://127.0.0.1:5000/api/
    ProxyPassReverse /api/ http://127.0.0.1:5000/api/
</VirtualHost>
```

**`/etc/apache2/sites-available/000-default.conf`** (port 80 only redirects). This replaces the `RewriteEngine`/`RewriteCond`/`RewriteRule` lines from the earlier README, so `mod_rewrite` is no longer needed.

```apache
<VirtualHost *:80>
    ServerName 172.16.10.114
    Redirect permanent / https://172.16.10.114/
</VirtualHost>
```

Apply:

```bash
apache2ctl configtest      # expect: Syntax OK
systemctl restart apache2
```

**Verify TLS behavior:**

```bash
cd /root/micro-ca/pki
# TLS 1.2 must fail
openssl s_client -connect 172.16.10.114:443 -tls1_2 -CAfile ca.crt </dev/null 2>&1 | grep -iE "alert|error"
# No client cert must fail
curl --cacert ca.crt https://172.16.10.114/api/challenge
# TLS 1.3 with a valid client cert must connect
openssl s_client -connect 172.16.10.114:443 -tls1_3 -CAfile ca.crt \
  -cert issued/HOST-SERIAL-001.crt -key private/HOST-SERIAL-001.key </dev/null 2>&1 | grep -E "Protocol|Verification"
```

---

## 5. Validation server and database (run on the Server)

Create `/root/validator/` and add three files.

### `db.py`

```python
import sqlite3

DB_PATH = "/root/validator/server_database.db"

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
        luks_key     TEXT NOT NULL,          -- escrowed key (protect/encrypt this DB in production)
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
```

### `server.py`

```python
import os
import secrets
import time

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from flask import Flask, abort, jsonify, request

from db import connect, init_db

ISSUED_DIR = os.environ.get("ISSUED_DIR", "/root/micro-ca/pki/issued")
NONCE_TTL = 30  # seconds
OAEP = padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)

app = Flask(__name__)
init_db()


def audit(db, event, host=None, cart=None, detail=""):
    db.execute("INSERT INTO audit VALUES (?,?,?,?,?)", (time.time(), event, host, cart, detail))
    db.commit()


def verified_cn():
    cn = request.headers.get("X-Client-CN")   # set by Apache from the verified client cert
    if not cn:
        abort(401)
    return cn


@app.post("/api/challenge")
def challenge():
    cn = verified_cn()
    body = request.get_json(force=True)
    host, cart = body.get("host_serial"), body.get("cartridge_id")
    db = connect()

    if host != cn:
        audit(db, "challenge_denied", host, cart, f"cert CN {cn} != claimed serial")
        return jsonify(error="certificate does not match serial"), 403

    ok = db.execute("""
        SELECT 1 FROM hosts h
        JOIN ownership o ON o.host_serial = h.host_serial
        JOIN cartridges c ON c.cartridge_id = o.cartridge_id
        WHERE h.host_serial = ? AND c.cartridge_id = ?
          AND h.is_active = 1 AND c.is_active = 1""", (host, cart)).fetchone()
    if not ok:
        audit(db, "challenge_denied", host, cart, "unknown/inactive/unpaired")
        return jsonify(error="host/cartridge not authorized"), 403

    nonce = secrets.token_hex(32)
    db.execute("INSERT INTO nonces (nonce, host_serial, cartridge_id, expires_at) VALUES (?,?,?,?)",
               (nonce, host, cart, time.time() + NONCE_TTL))
    db.commit()
    audit(db, "challenge_issued", host, cart)
    return jsonify(nonce=nonce, ttl=NONCE_TTL)


@app.post("/api/unlock")
def unlock():
    cn = verified_cn()
    body = request.get_json(force=True)
    nonce = body.get("nonce", "")
    try:
        signature = bytes.fromhex(body.get("signature", ""))
    except ValueError:
        return jsonify(error="bad signature encoding"), 400

    db = connect()
    row = db.execute("SELECT host_serial, cartridge_id FROM nonces WHERE nonce = ?", (nonce,)).fetchone()
    if not row or row["host_serial"] != cn:
        return jsonify(error="invalid nonce"), 400

    host, cart = row["host_serial"], row["cartridge_id"]

    # Atomic single-use consume: only one caller can flip used 0 -> 1, and only before expiry.
    cur = db.execute("UPDATE nonces SET used = 1 WHERE nonce = ? AND used = 0 AND expires_at > ?",
                     (nonce, time.time()))
    db.commit()
    if cur.rowcount != 1:
        audit(db, "replay_or_expired", host, cart, nonce[:8])
        return jsonify(error="nonce expired or already used"), 403

    # Verify the cartridge's signature using its certificate's public key
    try:
        with open(os.path.join(ISSUED_DIR, f"{cart}.crt"), "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        pub = cert.public_key()
        pub.verify(signature, bytes.fromhex(nonce), padding.PKCS1v15(), hashes.SHA256())
    except (InvalidSignature, FileNotFoundError):
        audit(db, "cartridge_auth_failed", host, cart)
        return jsonify(error="cartridge authentication failed"), 403

    luks_key = db.execute("SELECT luks_key FROM cartridges WHERE cartridge_id = ?", (cart,)).fetchone()[0]
    wrapped = pub.encrypt(luks_key.encode(), OAEP)   # only the real cartridge can unwrap this
    audit(db, "key_released", host, cart)
    return jsonify(wrapped_key=wrapped.hex())


if __name__ == "__main__":
    # Localhost only: Apache is the only thing that should reach this.
    app.run(host="127.0.0.1", port=5000)
```

### `provision.py` (registers a cartridge and prints a fresh key to stdout)

```python
import secrets
import sys

from db import connect, init_db

cart_id, host_serial, owner_id = sys.argv[1:4]
key = secrets.token_hex(32)

init_db()
db = connect()
db.execute("INSERT INTO cartridges (cartridge_id, luks_key) VALUES (?, ?)", (cart_id, key))
db.execute("INSERT OR IGNORE INTO hosts (host_serial, owner_id) VALUES (?, ?)", (host_serial, owner_id))
db.execute("INSERT OR IGNORE INTO ownership VALUES (?, ?)", (host_serial, cart_id))
db.commit()

sys.stdout.write(key)   # no newline: the exact bytes become the LUKS passphrase
```

Start the API (in its own terminal or a systemd unit):

```bash
cd /root/validator && python3 server.py
```

---

## 6. Provision the cartridge (Server → Cartridge, over SSH/scp)

This is the offline/factory step. In production it happens at manufacturing time, not over a live network.

**6.1 Copy identity material to the cartridge** (run on the Server). If you already did this in the earlier README, confirm the files are in place on the cartridge and skip the copy:

```bash
ssh root@172.16.10.116 'ls -l /etc/ssl/certs/ca.crt /etc/ssl/private/storage-cartridge.key'
```

Otherwise copy them, then move them into the standard locations (the daemon in section 8 reads the private key from `/etc/ssl/private/`):

```bash
scp /root/micro-ca/pki/ca.crt                          root@172.16.10.116:/root/
scp /root/micro-ca/pki/private/storage-cartridge.key   root@172.16.10.116:/root/
ssh root@172.16.10.116 '
  mv /root/ca.crt /etc/ssl/certs/
  mv /root/storage-cartridge.key /etc/ssl/private/
  chmod 600 /etc/ssl/private/storage-cartridge.key
'
```

> If you reissue the cartridge cert later, the server reads the **public** certificate from `/root/micro-ca/pki/issued/storage-cartridge.crt`, so the cartridge only ever needs the private key and the CA cert.

**6.2 Create the image, generate the key on the server, and LUKS-format** (run on the Server). This **replaces** the earlier `P@ssw0rd!` passphrase: the image is empty, so recreate it. The key travels over SSH into a shell variable on the cartridge and is never written to a file there:

```bash
ssh root@172.16.10.116 'rm -f /var/cartridge_storage.img; truncate -s 512M /var/cartridge_storage.img'

cd /root/validator
python3 provision.py storage-cartridge HOST-SERIAL-001 Company-User-A | ssh root@172.16.10.116 '
  K=$(cat)
  printf %s "$K" | cryptsetup luksFormat --batch-mode --key-file=- /var/cartridge_storage.img
  printf %s "$K" | cryptsetup luksOpen --key-file=- /var/cartridge_storage.img secure_cartridge
  mkfs.ext4 -q /dev/mapper/secure_cartridge
  cryptsetup luksClose secure_cartridge
  unset K
'
```

The server database now holds the escrowed key tied to `storage-cartridge` and its owner; the cartridge holds only the encrypted image and its private key.

> If `luksFormat` fails with a memory error in a small container, add `--pbkdf pbkdf2` to the `luksFormat` command.
> 
> To re-run provisioning from scratch, delete `/root/validator/server_database.db` first; `provision.py` refuses to register the same cartridge ID twice, and a new run generates a new key.

Optionally place a test file inside the volume once (unlock it via the full flow in section 10, write a file to `/mnt/cartridge_data`, then lock it).

---

## 7. Simulated serial link (socat)

If your link from the earlier README is still up and tested, **skip this section**. Otherwise (for example after restarting the containers):

**Cartridge** (run in its own terminal, or background it with `&`; a foreground `socat` blocks the prompt):

```bash
socat -d -d PTY,link=/dev/ttyV0,raw,echo=0 TCP-LISTEN:4000,reuseaddr,fork &
ls -l /dev/ttyV0
```

**Software host:**

```bash
socat -d -d PTY,link=/dev/ttyS_CARTRIDGE,raw,echo=0 TCP:172.16.10.116:4000 &
ls -l /dev/ttyS_CARTRIDGE
```

**Test the link** (cartridge: `cat < /dev/ttyV0`; host: `echo TEST_CARTRIDGE_LINK > /dev/ttyS_CARTRIDGE`). The string should appear on the cartridge. Stop the `cat` before starting the daemon.

---

## 8. Cartridge daemon (run on the Cartridge)

**`/opt/cartridge/cartridge_daemon.py`**

```python
#!/usr/bin/env python3
import os
import subprocess

import serial
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key

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


def unlock(key: bytes) -> str:
    if os.path.exists(f"/dev/mapper/{MAPPER}"):
        return "ALREADY_UNLOCKED"
    r = subprocess.run(["cryptsetup", "luksOpen", "--key-file=-", LUKS_IMAGE, MAPPER],
                       input=key, capture_output=True)
    if r.returncode != 0:
        print("[-] luksOpen failed:", r.stderr.decode().strip())
        return "FAILED"
    os.makedirs(MOUNT_POINT, exist_ok=True)
    m = subprocess.run(["mount", f"/dev/mapper/{MAPPER}", MOUNT_POINT], capture_output=True)
    if m.returncode != 0:
        print("[-] mount failed:", m.stderr.decode().strip())
        subprocess.run(["cryptsetup", "luksClose", MAPPER])
        return "FAILED"
    return "UNLOCKED"


def lock() -> str:
    subprocess.run(["umount", MOUNT_POINT], capture_output=True)
    subprocess.run(["cryptsetup", "luksClose", MAPPER], capture_output=True)
    return "LOCKED"


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
            except Exception as e:           # malformed input must never crash the daemon
                print("[-] error:", e)
                ser.write(b"STATUS:ERROR\n")


if __name__ == "__main__":
    main()
```

Run it as root: `python3 /opt/cartridge/cartridge_daemon.py`

---

## 9. Software host client (run on the Host)

Copy the host's identity from the server first. This uses the `HOST-SERIAL-001` cert from section 3.2; the old `consumer-software` cert (CN = IP address) will connect over mTLS but fails the server's serial check, so retire it.

```bash
# run on the Server
ssh root@172.16.10.115 'mkdir -p /etc/cartridge'
scp /root/micro-ca/pki/ca.crt                           root@172.16.10.115:/etc/cartridge/
scp /root/micro-ca/pki/issued/HOST-SERIAL-001.crt       root@172.16.10.115:/etc/cartridge/
scp /root/micro-ca/pki/private/HOST-SERIAL-001.key      root@172.16.10.115:/etc/cartridge/
```

**`software_host.py`**

```python
#!/usr/bin/env python3
import sys

import requests
import serial

SERVER = "https://172.16.10.114"
HOST_SERIAL = "HOST-SERIAL-001"
SERIAL_PORT = "/dev/ttyS_CARTRIDGE"
CERT = ("/etc/cartridge/HOST-SERIAL-001.crt", "/etc/cartridge/HOST-SERIAL-001.key")
CA = "/etc/cartridge/ca.crt"


def exchange(ser, line, prefix):
    ser.reset_input_buffer()
    ser.write((line + "\n").encode())
    reply = ser.readline().decode("utf-8", errors="ignore").strip()
    if not reply.startswith(prefix):
        raise RuntimeError(f"unexpected cartridge reply to {line[:12]!r}: {reply!r}")
    return reply[len(prefix):]


def post(path, payload):
    r = requests.post(f"{SERVER}{path}", json=payload, cert=CERT, verify=CA, timeout=5)
    if r.status_code != 200:
        raise RuntimeError(f"server rejected {path}: {r.status_code} {r.text.strip()}")
    return r.json()


def main():
    with serial.Serial(SERIAL_PORT, 115200, timeout=5) as ser:
        cartridge_id = exchange(ser, "ID?", "ID:")
        print(f"[*] Cartridge reports ID {cartridge_id}")

        nonce = post("/api/challenge", {"host_serial": HOST_SERIAL, "cartridge_id": cartridge_id})["nonce"]
        print("[+] Challenge received")

        signature = exchange(ser, f"CHALLENGE:{nonce}", "SIGNATURE:")
        print("[+] Cartridge signed the challenge")

        wrapped = post("/api/unlock", {"nonce": nonce, "signature": signature})["wrapped_key"]
        print("[+] Server verified cartridge and released wrapped key")

        ser.timeout = 30                      # LUKS key derivation can take a few seconds
        status = exchange(ser, f"KEY:{wrapped}", "STATUS:")
        print(f"[*] Cartridge status: {status}")
        sys.exit(0 if status in ("UNLOCKED", "ALREADY_UNLOCKED") else 1)


if __name__ == "__main__":
    main()
```

---

## 10. Run and verify

**Start order**

1. Server: Apache running; `python3 /root/validator/server.py`
2. Cartridge: `socat` listener, then `python3 /opt/cartridge/cartridge_daemon.py`
3. Host: `socat` connector, then `python3 software_host.py`

**Expected result:** host prints the four `[+]` lines and `UNLOCKED`; on the cartridge, `mount | grep cartridge_data` shows `/dev/mapper/secure_cartridge`, and `ls /mnt/cartridge_data` lists the volume. To re-lock for testing: `echo LOCK` through the host's serial port, or `umount /mnt/cartridge_data && cryptsetup luksClose secure_cartridge` on the cartridge.

**Security tests** (each should fail as described)

|Test|How|Expected|
|---|---|---|
|TLS 1.2 refused|`openssl s_client ... -tls1_2`|handshake failure|
|No client cert|`curl --cacert ca.crt https://172.16.10.114/api/challenge`|handshake failure|
|Replay|Capture a valid `/api/unlock` body and POST it again|`403 nonce expired or already used`|
|Expired nonce|Get a nonce, wait 35 s, then unlock|`403 nonce expired or already used`|
|Wrong cartridge / clone|Sign the nonce with a different RSA key|`403 cartridge authentication failed`|
|Spoofed serial|Host cert `HOST-SERIAL-001` sends `host_serial: HOST-SERIAL-002`|`403 certificate does not match serial`|
|Unpaired cartridge|Remove the `ownership` row, rerun|`403 host/cartridge not authorized`|
|Revoked host|`UPDATE hosts SET is_active=0 ...`, rerun|`403 host/cartridge not authorized`|
|Data at rest|`file /var/cartridge_storage.img` on the cartridge while locked|LUKS header, no readable plaintext|

Review activity with `sqlite3 /root/validator/server_database.db "SELECT * FROM audit ORDER BY ts DESC LIMIT 20;"`.

---

## 11. Troubleshooting

|Symptom|Cause / fix|
|---|---|
|`/etc/apache2` does not exist|Wrong terminal (probably the cartridge). Apache belongs on the server only.|
|`/dev/ttyV0` does not exist|`socat` is not running, or it is blocking a foreground terminal. Background it or use a second shell. If it exits with a PTY error, the container lacks `/dev/ptmx`; add `--device /dev/ptmx` or `--privileged`.|
|`requests` fails with a hostname/IP verification error|The server certificate lacks `IP:172.16.10.114` in its SAN. Reissue it as in section 3.|
|Flask fails to start on port 443|Port 443 belongs to Apache. Flask must listen on `127.0.0.1:5000`.|
|`401` from the API|The `X-Client-CN` header is missing, so the request did not come through Apache's mTLS vhost, or `mod_headers`/`mod_proxy_http` is not enabled.|
|`403 certificate does not match serial` using the old `consumer-software` cert|Its CN is `172.16.10.115`, not `HOST-SERIAL-001`. Use the cert from section 3.2, or register the CN you actually use in the database and in `software_host.py`.|
|`easyrsa` hangs at "Enter pass phrase"|That is the **CA** passphrase prompt for signing; it is expected.|
|`provision.py` fails with `UNIQUE constraint failed`|`storage-cartridge` is already registered. Delete `server_database.db` (section 6.2 note) to start over.|
|`cryptsetup luksOpen` fails in the container|Container lacks device-mapper access (needs privileges) or memory for the key derivation. See sections 2 and 6.2.|
|Serial reads time out|Host `socat` is not connected, or the cartridge daemon is not running. Test the raw link again (section 7).|

---

## 12. Known limitations (emulation vs. a real product)

- **Cartridge cloning.** The cartridge's private key sits in a file. Anyone who copies the image and the key can impersonate it. A real cartridge stores this key in a secure element or TPM and never exposes it. This is the biggest gap between the emulation and the anti-piracy goal.
- **Key escrow.** LUKS keys are stored in the server's SQLite database in the clear. Production should keep them in an HSM/KMS or encrypt them under a key not stored in the same place.
- **"In memory" caveat.** Once the volume is mounted, plaintext is served through the kernel page cache. It is never written to disk unencrypted, but it is not strictly RAM-only, and the authorized host can read it (by design).
- **CA hygiene.** Your CA is already passphrase-protected, which is the right choice. Ideally keep the root CA offline with a separate issuing CA, and add certificate revocation (CRL/OCSP) beyond the database `is_active` flag.
- **Secrets in notes.** The earlier README records the CA passphrase and the old LUKS passphrase in plain text. Remove them from the README (and its version history if it is in git), and treat the CA passphrase as compromised if that file was shared.
- **Serial transport.** The wrapped key and signatures are safe to observe, but add message framing, length limits, and a rate limit on `/api/challenge`.
- **Operations.** Run the API under `gunicorn`/systemd rather than the Flask dev server, and purge expired rows from `nonces` periodically.
- **Original `shred` step removed.** `shred` is unreliable on journaling filesystems and SSDs; this runbook avoids the problem by never writing the key to the cartridge.

---
# Running the Cartridge Project: CLI Step-by-Step

This guide takes the lab from containers to a working unlock, entirely from the command line. It assumes the scripts in your README with the fixes in **Step 0** applied.

> **Use bash, not fish**, on all four machines. Several commands below (`$(...)`, `${PIPESTATUS[*]}`, multi-line quoting) break in fish. Run `bash` after logging in if needed.

## Machines and terminals

|Label|Where|What runs there|
|---|---|---|
|**[PVE]**|Proxmox node shell|Container settings only|
|**[S]**|CT 410, `172.16.10.114`|CA, Apache, validator API, database|
|**[P]**|CT 411, `172.16.10.115`|Software host, serial link (host side)|
|**[C]**|CT 412, `172.16.10.116`|Encrypted image, serial link (cartridge side), daemon|

You will have three long-running processes, each needing its own terminal: the **API** on [S], and `socat` + the **daemon** on [C]. The `socat` on [P] needs one too. Open extra shells (or use `tmux`) when a step says **"own terminal"**.

---

## Step 0. Fix the README first

| #   | File / line                     | Problem                                                                                                                    | Fix                                                                      |
| --- | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| 1   | `server.py` ~L338 (`challenge`) | `db.connect()` never assigns `db`, so every `/api/challenge` crashes                                                       | `db = connect()`                                                         |
| 2   | `server.py` ~L374 (`unlock`)    | `(Nonce,)` is undefined, and `.fetchone` is never called                                                                   | `(nonce,)).fetchone()`                                                   |
| 3   | `server.py` ~L394               | `FileNoteFoundError` is undefined                                                                                          | `FileNotFoundError`                                                      |
| 4   | `software-host.py` ~L452        | `def exchange():` has no parameters but is called with three                                                               | `def exchange(ser, line, prefix):`                                       |
| 5   | `cartridge_daemon.py` ~L506     | `cryptography.hazmat.prevents...` is not a module                                                                          | `cryptography.hazmat.primitives.serialization`                           |
| 6   | `cartridge_daemon.py` ~L542     | `subprocess.rum`                                                                                                           | `subprocess.run`                                                         |
| 7   | README ~L574                    | Run line says `cartridge-daemon.py`, file is `cartridge_daemon.py`                                                         | Use `cartridge_daemon.py` everywhere                                     |
| 8   | README ~L19                     | Package `sqlite` doesn't exist on Debian                                                                                   | `sqlite3`; also install the Python packages in Step 2                    |
| 9   | README ~L175                    | `vim /etc/pve/lxc/412.con`                                                                                                 | `412.conf`                                                               |
| 10  | README ~L180                    | A trailing `# comment` on an LXC config line is parsed as part of the value                                                | Put the comment on its own line                                          |
| 11  | README ~L24–27                  | Self-signed `apache-selfsigned` cert is generated but never used                                                           | Delete that step                                                         |
| 12  | README ~L131–134                | `a2enmod` and the Apache restart sit under the cartridge section, and the restart comes **before** the modules are enabled | Run on the server, enable modules first, then restart (Step 5)           |
| 13  | README (missing)                | No step creates `/var/cartridge_storage.img` after the `dd` line was removed                                               | Added in Step 7                                                          |
| 14  | README ~L75, 81, 88, 93         | CA passphrase written in plain text                                                                                        | Replace with a placeholder; change the passphrase if the file was shared |

---

## Step 1. Proxmox: let CT 412 use device-mapper and loop devices

**[PVE]**

```bash
modprobe dm_mod dm_crypt loop
grep device-mapper /proc/devices      # note the number, e.g. 252
ls -l /dev/mapper/control /dev/loop-control   # expect c 10,236 and c 10,237
pct stop 412
nano /etc/pve/lxc/412.conf
```

Append (replace `252` with the number you found; comments must be on their own lines):

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
losetup -f                                   # must print /dev/loop0 with no "(lost)"
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
# Create db.py, server.py and provision.py from the README (with the Step 0 fixes)
python3 -m py_compile db.py server.py provision.py && echo "syntax OK"
rm -f server_database.db                     # always start provisioning from a clean database
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
# Create /opt/cartridge/cartridge_daemon.py from the README (with the Step 0 fixes)
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

| Symptom                                             | Cause / fix                                                                                                    |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `Cannot initialize device-mapper`                   | `dm_mod` not loaded on the host, or CT 412 not privileged / missing mount entry (Step 1)                       |
| `Attaching loopback device failed`                  | No `/dev/loopN` nodes in the container (Step 6)                                                                |
| `mkfs.ext4: Operation not permitted`                | Wrong device-mapper major in `412.conf`; restart the container fully                                           |
| `UNIQUE constraint failed: cartridges.cartridge_id` | Stale registration; delete `server_database.db` and re-provision                                               |
| `ModuleNotFoundError: serial`                       | `apt install python3-serial` on that machine                                                                   |
| `SSLError ... doesn't match` / IP mismatch          | Server cert has no `IP:172.16.10.114` SAN (Step 3)                                                             |
| `curl` returns `503`                                | Flask isn't running on `127.0.0.1:5000`                                                                        |
| `403 Certificate does not match the serial`         | Host cert CN isn't `HOST-SERIAL-001`                                                                           |
| Cartridge status `FAILED`                           | Key in the database doesn't match the image; reset and re-provision. The daemon prints the `cryptsetup` error. |
| Host script hangs on serial                         | Both `socat` processes and the daemon must be running (Step 8, 9)                                              |
| `could not open port /dev/ttyS_CARTRIDGE`           | `socat` on [P] isn't running                                                                                   |