#!/usr/bin/env bash
# Name: phase0-validations.sh
# Nodes: Host
# Purpose: Verify that all aspects of Phase 0 are implemented in the project docker containers
# Notes:
#   - Section 1 - Design Attributes
#       - One Trust Anchor (Offline)
#       - Per-Device Identities
#       - Roles
#       - Key Separation
#       - Software Key Storage (ES-256-GCM)
#       - Compact Certificate Format (Serial, Role, Model, PK, Validity, Issuer Signature)
#       - Modern Small Algorithms (Ed25519 and X25519)
#       - Device Registry (Serial, Role, Model, and Status)
#   - Section 2 - Protocols
#       - Root Generattion (Offline)
#       - Update Keys (Offline)
#       - Device Key Generation
#       - Cert Issuance
#       - Image Assembly
#       - Registration
#   - Section 3 - Implementations
#       - Pinned Crypto Library
#       - Defined Cert Format
#       - Offline Issuer Tool
#       - Generated Update Keys
#       - Software Key Storage
#       - Provisioning Flow
#       - Device Registry
#       - Unit-Tested the Trust Checks
# ===================================================================
# Setup

set -u
export RUNTIME=docker
ISS="docker exec acme-issuer /opt/acme/bin/acme-issuer"
REG="docker exec acme-server /opt/acme/bin/acme-registry"
status() { docker exec "$1" /opt/acme/bin/acme-device status; }

section() {
  echo ""
  echo "======================================================================"
  echo "$1"
}

step() {
  echo ""
  echo "----------------------"
  echo ">> $1"
  echo "----------------------"
}

for c in acme-server acme-console acme-cartridge; do
    docker exec "$c" test -f /var/lib/acme-device/device.cert \
    || { echo "FATAL: $c is not provisioned. Run provision.sh first."; exit 1; }
done
docker exec acme-provision test -f /var/lib/acme-station/trust/root.cert |
    || { echo "FATAL: station has no trust anchor"; exit 1}

#echo "> :"
# ===================================================================
# Section 1: Design Attributes

section "Section 1: Design Attributes"

# ===============================
step "One Trust Anchor (Offline)"

echo "> Should print 'lo':"
docker exec acme-issuer ls /sys/class/net

echo "> Print the network status of each container:"
for c in acme-issuer acme-provision acme-server acme-console acme-cartridge; do
  echo "$c: $(docker inspect -f '{{.HostConfig.NetworkMode}}' "$c")"
done

echo "> One root cert eberywhere, all hashes should look identical:"
for entry in \
  acme-issuer:/var/lib/acme-issuer/root/root.cert \
  acme-provision:/var/lib/acme-station/trust/root.cert \
  acme-server:/var/lib/acme-device/root.cert \
  acme-console:/var/lib/acme-device/root.cert \
  acme-cartridge:/var/lib/acme-device/root.cert; do
  docker exec "${entry%%:*}" sha256sum "${entry#*:}"
done

echo "> The root PK exists only in the issuer:"
for c in acme-provision acme-server acme-console acme-cartridge; do
  echo "$c: $(docker exec "$c" find /var/lib -name root.key | wc -l) root.key files"
done

echo "> Self-signed, role is root and the issuer serial equals its own serial:"
$ISS show /var/lib/acme-issuer/root/root.cert

# ===============================
step "Per-Device Identities"

echo "> Print out identites. All have a different serial and PK (Note: Phase 0 does not revocation yet so the status column in the reg are for later:"
for c in acme-server acme-console acme-cartridge; do
  echo "== $c"
  status "$c" | grep -E 'serial|role|sign_pk'
done

docker exec acme-server python3 -c "
from pathlib import Path
from acme import cert as C
from acme.cert import Role
anchor = C.load_trust_anchor(Path('/var/lib/acme-device/root.cert').read_bytes())
raw = Path('/var/lib/acme-device/device.cert').read_bytes()
mine = C.verify_cert(raw, anchor, Role.SERVER)
print('accepted:', mine.serial_hex)
try:
    C.verify_cert(raw, anchor, Role.SERVER, is_revoked=lambda s: s == mine.serial)
except C.CertError as e:
    print('revoked ->', e)
"

# ===============================
step "Roles"

docker exec acme-cartridge python3 -c "
from acme import cert as C
from acme.cert import Role
anchor = C.load_trust_anchor(open('/var/lib/acme-device/root.cert','rb').read())
raw = open('/var/lib/acme-device/device.cert','rb').read()
for r in (Role.CARTRIDGE, Role.CONSOLE, Role.SERVER):
    try:
        C.verify_cert(raw, anchor, r)
        print(r.name, 'accepted')
    except C.CertError as e:
        print(r.name, 'rejected:', e)
"

docker exec acme-provision python3 -c "
from acme import crypto, csr as R
from acme.cert import Role
sk, _ = crypto.sign_keygen()
try:
    R.make_csr(sk, serial=crypto.random(16), role=Role.UPDATE, model='X')
except Exception as e:
    print('refused:', e)
"

# ===============================
step "Key Separation"

echo "> Console, two SK; Server and Cartridge, one SK:"
for c in acme-console acme-server acme-cartridge; do
  echo "== $c"
  docker exec "$c" ls /var/lib/acme-device | grep -E 'key.enc|update'
done
status acme-console | grep -E 'sign_pk|enc_pk|update certs|private keys'

echo "> Update keys live apart from the issueing key, with diff PK:"
docker exec acme-issuer ls -l /var/lib/acme-issuer/root /var/lib/acme-issuer/update
$ISS show /var/lib/acme-issuer/root/root.cert /var/lib/acme-issuer/update/primary.cert | grep -E 'model|sign_pk'

# ===============================
step "Software Key Storage (AES-256-GCM)"

echo "> Software Storage keys (file is 60-bytes: 12-byte nonce, 32-byte key encrypt, and 16-byte GCM tag):"
docker exec acme-cartridge ls -l /var/lib/acme-device
docker exec acme-cartridge wc -c /var/lib/acme-device/sign.key.enc
docker exec acme-cartridge od -An -tx1 /var/lib/acme-device/sign.key.enc
status acme-cartridge | grep 'private keys'

echo "> Tamper test (copy of /tmp/img):"
docker exec acme-cartridge cp -r /var/lib/acme-device /tmp/img
docker exec acme-cartridge python3 -c "
p='/tmp/img/sign.key.enc'; b=bytearray(open(p,'rb').read()); b[-1]^=1; open(p,'wb').write(b)"

docker exec acme-cartridge /opt/acme/bin/acme-device --home /tmp/img status || true
docker exec acme-cartridge rm -rf /tmp/img

echo "> KEK Recompute Check (Obfuscation, not protection), recomputing the KEK from files already on the device and prints whether it matches:"
docker exec acme-cartridge python3 -c "
from pathlib import Path
from acme import keystore as K, crypto, cert as C
d = Path('/var/lib/acme-device')
role = K.DeviceImage(d).role()
cert = C.verify_cert((d/'device.cert').read_bytes(), C.load_trust_anchor((d/'root.cert').read_bytes()), role)
kek = K._kek((d/'device.secret').read_bytes(), role, cert.serial)
sk = crypto.aead_decrypt(kek, (d/'sign.key.enc').read_bytes(), K._aad(cert.serial, 'sign'))
print('recovered key matches certificate:', crypto.sign_public(sk) == cert.sign_pk)
"

# ===============================
step "Compact Certificate Format"

$ISS show /var/lib/acme-issuer/root/root.cert
docker exec acme-cartridge python3 -c "
import cbor2
raw = open('/var/lib/acme-device/device.cert','rb').read()
tbs, sig = cbor2.loads(raw)
print('total bytes:', len(raw), ' signature bytes:', len(sig))
for k, v in cbor2.loads(tbs).items():
    print(k, v.hex() if isinstance(v, bytes) else v)
"

echo "> keys 1 to 9 are version, serial, role, model, signing key, validity (7 and 8), and issuer; key 6 is the console-only encryption key. The whole certificate is well under the 512-byte limit. The parser is strict:"
docker exec acme-cartridge python3 -c "
from acme import cert as C
from acme.cert import Role
anchor = C.load_trust_anchor(open('/var/lib/acme-device/root.cert','rb').read())
raw = open('/var/lib/acme-device/device.cert','rb').read()
for name, bad in (('trailing byte', raw + b'\x00'), ('truncated', raw[:-1])):
    try:
        C.verify_cert(bad, anchor, Role.CARTRIDGE)
    except C.CertError as e:
        print(name, '->', e)
"
# ===============================
step "Modern Small Algorithms (Ed25519 and X25519)"

docker exec acme-console python3 -c "
from acme import crypto as c
print('sign_pk', c.SIGN_PK_LEN, 'sig', c.SIG_LEN, 'dh_pk', c.DH_PK_LEN, 'bytes')
a_sk, a_pk = c.dh_keygen(); b_sk, b_pk = c.dh_keygen()
print('X25519 both sides agree:', c.dh(a_sk, b_pk) == c.dh(b_sk, a_pk))
sk, pk = c.sign_keygen(); s = c.sign(sk, b'hi')
print('Ed25519 good/tampered:', c.verify(pk, b'hi', s), c.verify(pk, b'ho', s))
"
docker exec acme-console python3 -c "import nacl, cryptography; print('libsodium binding', nacl.__version__, '/ cryptography', cryptography.__version__)"

# ===============================
step "Device Registry"

echo "> Only accepts certs that are ACME signed (Five rows: server, console, cartridge, two update keys; all active and the junk cert is REJECTED):"
$REG list
docker exec acme-server sqlite3 -header -column /var/lib/acme-server/registry.db \
  "SELECT serial, role, model, status FROM devices;"
docker exec acme-server sqlite3 /var/lib/acme-server/registry.db .schema

docker exec acme-server sh -c 'mkdir -p /tmp/bad && echo junk > /tmp/bad/x.cert && /opt/acme/bin/acme-registry import /tmp/bad; echo "exit=$?"; rm -rf /tmp/bad'

# ===================================================================
# Section 2: Protocols

section "Section 2: Protocols"

# ===============================
step "Root Generation and Update Keys (Offline)"

echo "> One root line, two update lines:"
$ISS list
docker exec acme-issuer ls -l /var/lib/acme-issuer/root /var/lib/acme-issuer/update

echo "> Refuse to overwrite:"
$ISS init-root; echo "exit=$?"

echo "> Same:"
$ISS init-update-keys; echo "exit=$?"

echo "> Air-gap guard check via throwawy container (Refuses before generating anything):"
docker run --rm acme-phase0:latest /opt/acme/bin/acme-issuer init-root; echo "exit=$?"

# ===============================
step "Device Key Generation (Scratch Image)"

echo "> Use a scratch image so the real console is untouched. The device generates its own keys, and status says 'state:pending'. The request holds public data and the proof of possession; show labels it 'type: request':"
docker exec acme-console /opt/acme/bin/acme-device --home /tmp/demo init \
  --role console --model DEMO-CONSOLE --csr-out /tmp/demo-out/request.csr
docker exec acme-console ls -l /tmp/demo
docker exec acme-console /opt/acme/bin/acme-device --home /tmp/demo status
docker exec acme-console /opt/acme/bin/acme-issuer show /tmp/demo-out/request.csr

# ===============================
step "Cert Issuance & Duplicate Rejection"

echo "> Leave a DEMO-CONSOLE entry in the issuer's append-only log, which is harmless and identifiable:"
docker exec acme-issuer mkdir -p /srv/demo-in
docker cp acme-console:/tmp/demo-out/request.csr ./demo.csr
docker cp ./demo.csr acme-issuer:/srv/demo-in/demo.csr
$ISS sign /srv/demo-in /srv/demo-out
docker exec acme-issuer sh -c '/opt/acme/bin/acme-issuer show /srv/demo-out/*.cert'
$ISS sign /srv/demo-in /srv/demo-out; echo "exit=$?"

echo "> Cleaning up demo CSR/Cert files:"
docker exec acme-console rm -rf /tmp/demo /tmp/demo-out
docker exec acme-issuer rm -rf /srv/demo-in /srv/demo-out
rm -f demo.csr

# ===============================
step "Image Assembly and Registration (Re-provisioning Cartridge)"

echo "> Runs the whole flow with a heading per step, erase the cartridge and provision it again:"
docker exec acme-cartridge /opt/acme/bin/acme-device erase
./provision.sh cartridge CART-DEMO


echo "> Station generates keys, issuer signs, station verifies, image assembly, station erasing its copy, and registration:"

echo "> Image contents:"
docker exec acme-cartridge ls -l /var/lib/acme-device

echo "> Comapre, console has more:"
docker exec acme-console ls -l /var/lib/acme-device

echo "> No 'keys held':"
docker exec acme-provision /opt/acme/bin/acme-station list

echo "> Empty:"
docker exec acme-provision ls /var/lib/acme-station/work

echo "> New cartridge row:"
$REG list

echo "> Prints 'known':"
docker exec acme-server /opt/acme/bin/acme-registry import /srv/reg

# ===================================================================
# Section 3: Implementations

section "Section 3: Implementations"

# ===============================
step "Implementation & Code Checks"

echo "> Pinned Crypto Library; lists only 'crypto.py'. Every other file calls its functions:"
docker exec acme-issuer grep -rlE "^(from|import) (nacl|cryptography)" /opt/acme/acme

echo "> Defined Cert Format, Shows the format header:"
docker exec acme-issuer sed -n '1,20p' /opt/acme/acme/cert.py

echo "> Offline Issuer Tool, the console's 'update certs 2' from status:"
$ISS --help
status acme-console | grep -E 'update certs|private keys'

echo "> Provisioning usage and status:"
./provision.sh || true
./provision.sh status

# ===============================
step "Unit-Tested Trust Checks"

docker exec acme-provision python3 -m pytest -q -p no:cacheprovider
docker exec acme-provision python3 -m pytest tests/test_cert.py -v -p no:cacheprovider \
  -k "wrong_signer or wrong_role or expired or not_yet_valid or revoked or garbage or malformed"
