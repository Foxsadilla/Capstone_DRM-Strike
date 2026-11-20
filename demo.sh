#!/usr/bin/env bash
# ===================================================================
# Name: demo.sh
# Nodes: Host (the machine running Docker)
# Purpose: Guided, end-to-end demonstration of ACME Phase 0 (Trust Foundation).
#          Combines test-setup.sh, provision.sh and phase0-validations.sh.
# Usage:
#   ./demo.sh               fresh run: resets every container, then builds,
#                           creates keys, provisions and validates
#   ./demo.sh --keep        skip the reset, key creation and provisioning;
#                           demonstrate the validations on existing containers
#   ./demo.sh --no-pause    run straight through (also automatic when not
#                           attached to a terminal)
#   ./demo.sh --no-color    plain text (also NO_COLOR=1, or when piped)
#   Save a copy:  ./demo.sh 2>&1 | tee demo-output.txt   (pauses still work;
#                 colours are left out of the saved file)
# Notes:
#   - A fresh run deletes the root key and every identity (docker compose down -v).
#   - At any "Press Enter" prompt, type q then Enter to stop.
# ===================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$ROOT/docker"
BIN=/opt/acme/bin
ISSUER=acme-issuer STATION=acme-provision SERVER=acme-server CONSOLE=acme-console CARTRIDGE=acme-cartridge

PAUSE=1 COLOR=1 KEEP=0
for a in "$@"; do
  case "$a" in
    --keep) KEEP=1 ;;
    --no-pause|-y) PAUSE=0 ;;
    --no-color) COLOR=0 ;;
    -h|--help) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $a (try --help)" >&2; exit 1 ;;
  esac
done
[ -t 1 ] || COLOR=0
[ -n "${NO_COLOR:-}" ] && COLOR=0
# Pause only when a keyboard is available (works even when output is piped to tee)
{ : </dev/tty; } 2>/dev/null || PAUSE=0

# ------------------------------------------------------------------- colours
if [ "$COLOR" = 1 ]; then
  C_SEC=$'\e[1;97;45m'   # section banner:  white on magenta
  C_STEP=$'\e[1;96m'     # step heading:  cyan
  C_DEV=$'\e[1;92m'      # devices involved:  green
  C_NOTE=$'\e[33m'       # explanation notes: yellow
  C_CMD=$'\e[1;94m'      # the command about to run:  blue
  C_OK=$'\e[1;92m'       # expected result confirmed:  green
  C_BAD=$'\e[1;91m'      # rejection or error: red
  C_PAUSE=$'\e[1;30;107m' # press-enter prompt: black on white
  C_DIM=$'\e[2m' C_OFF=$'\e[0m'
else
  C_SEC= C_STEP= C_DEV= C_NOTE= C_CMD= C_OK= C_BAD= C_PAUSE= C_DIM= C_OFF=
fi

# ------------------------------------------------------------------- display helpers
section() {   # section "Title" "one-line purpose"
  local line; line=$(printf '%*s' 72 '' | tr ' ' '=')
  printf '\n\n%s%s%s\n' "$C_SEC" "$(printf ' %-71s' "$1")" "$C_OFF"
  [ -n "${2:-}" ] && printf '%s %s%s\n' "$C_SEC" "$(printf '%-71s' "$2")" "$C_OFF"
  printf '%s%s%s\n' "$C_DIM" "$line" "$C_OFF"
}
step() {      # step "2.1" "Title"
  printf '\n%s>> %s  %s%s\n' "$C_STEP" "$1" "$2" "$C_OFF"
  printf '%s%s%s\n' "$C_DIM" "------------------------------------------------------------------------" "$C_OFF"
}
devices() { printf '%sDevices:%s %s\n' "$C_DEV" "$C_OFF$C_DEV" "$*$C_OFF"; }
note() {      # each argument is one line of explanation
  local l; for l in "$@"; do printf '%s| %s%s\n' "$C_NOTE" "$l" "$C_OFF"; done
}
show() { printf '%s$ %s%s\n' "$C_CMD" "$*" "$C_OFF"; }       # display a command
argv() {   # display argv as typed: 'ct' becomes 'docker exec', spaced args get quotes
  local out="" x; [ "$1" = ct ] && { out="docker exec"; shift; }
  for x in "$@"; do case "$x" in *" "*) x="\"$x\"" ;; esac; out="${out:+$out }$x"; done
  show "$out"
}
run()  { argv "$@"; "$@"; }                                  # display, then run
ok()   { printf '%s[OK] %s%s\n' "$C_OK" "$*" "$C_OFF"; }
bad()  { printf '%s[REJECTED, AS EXPECTED] %s%s\n' "$C_BAD" "$*" "$C_OFF"; }
die()  {
  printf '\n%s[STOPPED] %s%s\n' "$C_BAD" "$1" "$C_OFF" >&2
  printf '%sTo start over: ./demo.sh  (resets every container)%s\n' "$C_NOTE" "$C_OFF" >&2
  exit 1
}
pause() {
  [ "$PAUSE" = 1 ] || return 0
  local r
  printf '\n%s  Press Enter to continue (q + Enter to quit)  %s ' "$C_PAUSE" "$C_OFF"
  read -r r </dev/tty || r=
  case "$r" in q|Q) printf '%sDemo stopped.%s\n' "$C_NOTE" "$C_OFF"; exit 0 ;; esac
}
expect_fail() {   # expect_fail "what is rejected" cmd args...  (stderr shown inline)
  argv "${@:2}"
  local rc; "${@:2}" 2>&1; rc=$?
  if [ "$rc" -ne 0 ]; then bad "$1 (exit code $rc)"; else printf '%s[UNEXPECTED] command succeeded%s\n' "$C_BAD" "$C_OFF"; fi
}

# ------------------------------------------------------------------- provisioning helpers (from provision.sh)
ct() { local id=$1; shift; docker exec "$id" "$@"; }
# carry SRC SRC_DIR DST DST_DIR: tar stream piped through the host, standing in for
# removable media. Nothing is written on the host, so file ownership never breaks.
carry() {
  ct "$3" sh -c "rm -rf $4 && mkdir -p $4" &&
  docker exec "$1" tar cf - -C "$2" . | docker exec -i "$3" tar xf - -C "$4" --no-same-owner
}
serial_of() { sed -n 's/^serial=//p' | tr -d '\r'; }

prov_trust() {
  run ct "$ISSUER" $BIN/acme-issuer export-public /srv/public || die "export-public failed"
  show "carry acme-issuer:/srv/public -> acme-provision:/srv/trust"
  carry "$ISSUER" /srv/public "$STATION" /srv/trust || die "transfer failed"
  run ct "$STATION" $BIN/acme-station trust /srv/trust || die "station could not load the trust anchor"
}
prov_keys_self() {   # ROLE DEVICE MODEL -> sets SERIAL
  local out
  ct "$2" rm -rf /srv/out
  show "docker exec $2 $BIN/acme-device init --role $1 --model $3 --csr-out /srv/out/request.csr"
  out=$(ct "$2" $BIN/acme-device init --role "$1" --model "$3" --csr-out /srv/out/request.csr) || die "key generation failed on $2 (already provisioned? start over)"
  echo "$out"; SERIAL=$(serial_of <<<"$out")
  run ct "$2" ls -l /var/lib/acme-device
  show "carry $2:/srv/out -> acme-provision:/srv/in"
  carry "$2" /srv/out "$STATION" /srv/in || die "transfer failed"
  run ct "$STATION" $BIN/acme-station accept /srv/in/request.csr || die "station refused the request"
}
prov_keys_cart() {   # MODEL -> sets SERIAL
  local out
  show "docker exec $STATION $BIN/acme-station new-cartridge --model $1"
  out=$(ct "$STATION" $BIN/acme-station new-cartridge --model "$1") || die "cartridge key generation failed"
  echo "$out"; SERIAL=$(serial_of <<<"$out")
}
prov_issue() {
  ct "$STATION" rm -rf /srv/out
  run ct "$STATION" $BIN/acme-station export-requests /srv/out || die "export-requests failed"
  show "carry acme-provision:/srv/out -> acme-issuer:/srv/inbox"
  carry "$STATION" /srv/out "$ISSUER" /srv/inbox || die "transfer failed"
  ct "$ISSUER" rm -rf /srv/outbox
  run ct "$ISSUER" $BIN/acme-issuer sign /srv/inbox /srv/outbox || die "the issuer rejected a request (a leftover from a failed run? start over)"
  show "carry acme-issuer:/srv/outbox -> acme-provision:/srv/in"
  carry "$ISSUER" /srv/outbox "$STATION" /srv/in || die "transfer failed"
  run ct "$STATION" $BIN/acme-station receive /srv/in || die "the station rejected a certificate (did the trust step run?)"
}
prov_image() {       # SERIAL DEVICE [install args]
  local s=$1 d=$2; shift 2
  ct "$STATION" rm -rf /srv/out
  run ct "$STATION" $BIN/acme-station export "$s" /srv/out || die "export failed"
  show "carry acme-provision:/srv/out -> $d:/srv/in"
  carry "$STATION" /srv/out "$d" /srv/in || die "transfer failed"
  ct "$STATION" $BIN/acme-station wipe-dir /srv/out
  run ct "$d" $BIN/acme-device install /srv/in "$@" || die "install failed on $d"
  ct "$d" $BIN/acme-station wipe-dir /srv/in
}
prov_register() {    # SERIAL
  ct "$STATION" rm -rf /srv/reg
  show "copy certs/$1.cert and both update certificates to /srv/reg on the station"
  ct "$STATION" sh -c "mkdir -p /srv/reg && cp /var/lib/acme-station/certs/$1.cert /var/lib/acme-station/trust/update-*.cert /srv/reg/" || die "copy failed"
  show "carry acme-provision:/srv/reg -> acme-server:/srv/reg"
  carry "$STATION" /srv/reg "$SERVER" /srv/reg || die "transfer failed"
  run ct "$SERVER" $BIN/acme-registry import /srv/reg || die "the registry rejected a certificate"
}
status_all() {
  local d
  for d in "$SERVER" "$CONSOLE" "$CARTRIDGE"; do
    printf '\n%s== %s%s\n' "$C_STEP" "$d" "$C_OFF"; ct "$d" $BIN/acme-device status
  done
  printf '\n%s== Station (acme-provision)%s\n' "$C_STEP" "$C_OFF"; ct "$STATION" $BIN/acme-station list
  printf '\n%s== Registry (acme-server)%s\n' "$C_STEP" "$C_OFF"; ct "$SERVER" $BIN/acme-registry list
}
dstatus() { docker exec "$1" $BIN/acme-device status; }

# ------------------------------------------------------------------- preflight
command -v docker >/dev/null || die "docker not found"
docker info >/dev/null 2>&1 || die "cannot reach Docker (is it running, and is your user in the docker group?)"
[ -f "$DOCKER_DIR/.env" ] || die "docker/.env not found next to this script ($DOCKER_DIR)"

# =================================================================== INTRO
section "ACME PHASE 0: TRUST FOUNDATION, GUIDED DEMO" "Five containers, one offline root key, three provisioned devices"
note "Phase 0 creates everything later phases rely on: who is trusted, which keys exist," \
     "what each key may be used for, and where keys live. Nothing here uses a network:" \
     "files move between containers through the host, standing in for removable media." \
     "" \
     "Containers:" \
     "  acme-issuer     ACME's air-gapped issuer: root key and update keys (no network)" \
     "  acme-provision  manufacturing and provisioning station (no network)" \
     "  acme-server     server identity and the device registry (acme-net)" \
     "  acme-console    console identity: signing + encryption keys (acme-net)" \
     "  acme-cartridge  cartridge identity: signing key only (no network)" \
     "" \
     "Colours:  section banners | step headings | Devices | notes | \$ commands | prompts." \
     "Uncoloured text is the real output of the command shown above it."
if [ "$KEEP" = 1 ]; then
  note "" "--keep: using the existing containers. Parts 1 to 3 are skipped."
else
  printf '%s| WARNING: this run deletes every key and identity and starts fresh.%s\n' "$C_BAD" "$C_OFF"
  note "To demonstrate on the existing containers instead, quit and run: ./demo.sh --keep"
fi
pause

if [ "$KEEP" = 0 ]; then
# =================================================================== PART 1
section "PART 1: BUILD AND START THE CONTAINERS" "Replaces test-setup.sh's reset; uses docker/.env to manage all five at once"

step "1.1" "Reset: remove the containers and every volume"
devices "all five containers"
note "docker compose down -v stops the containers and deletes their volumes, including" \
     "the old root key and every device identity, so the demo starts from nothing."
show "cd docker && docker compose down -v"
( cd "$DOCKER_DIR" && docker compose down -v ) || die "docker compose down failed"
ok "All containers and volumes removed"
pause

step "1.2" "Build the image and start the containers"
devices "all five containers"
note "One image, acme-phase0:latest (Debian 13 + PyNaCl, cryptography, cbor2, pytest," \
     "sqlite3 + the project code), runs in all five containers. Lines marked CACHED" \
     "reuse layers from an earlier build. Each container gets new, empty volumes."
show "cd docker && docker compose up -d --build"
( cd "$DOCKER_DIR" && docker compose up -d --build ) || die "docker compose up failed"
pause

step "1.3" "Confirm all five are running, and their networks"
devices "all five containers"
note "What you see: each container's name and state, then its network mode." \
     "Meaning: issuer, provision and cartridge have NO network ('none'); only the server" \
     "and console share 'acme-net', which they will use from Phase 1."
show "cd docker && docker compose ps"
( cd "$DOCKER_DIR" && docker compose ps --format 'table {{.Name}}\t{{.State}}\t{{.Status}}' )
for c in $ISSUER $STATION $SERVER $CONSOLE $CARTRIDGE; do
  printf '%-15s network: %s\n' "$c" "$(docker inspect -f '{{.HostConfig.NetworkMode}}' "$c")"
done
pause

# =================================================================== PART 2
section "PART 2: TRUST ANCHOR (STEPS 0.1 AND 0.2)" "Run inside the air-gapped issuer, which refuses to work with a network"

step "2.1" "Step 0.1: generate the root key and self-sign Cert_ACME"
devices "acme-issuer"
note "The issuer first checks it has no network interface, then generates an Ed25519" \
     "key pair and signs its own certificate. This is the ONE trust anchor every device" \
     "will check against. Look for:" \
     "  serial     16 random bytes (32 hex characters): the root's ID" \
     "  role root  only the self-signed anchor has this role" \
     "  sign_pk    the root public key every device verifies against" \
     "  not_after  20 years (7,300 days) after not_before" \
     "  issuer     equal to its own serial: self-signed"
run ct "$ISSUER" $BIN/acme-issuer init-root || die "init-root failed (root already exists? start over)"
pause

step "2.2" "Step 0.2: generate the primary and backup update keys"
devices "acme-issuer"
note "Two more key pairs, each certified by the root with role 'update'. They will sign" \
     "firmware in Phase 3, so routine releases never touch the root key. The backup is" \
     "pre-installed in consoles as a recovery path if the primary leaks. Look for:" \
     "  role update, different sign_pk values, validity 10 years, issuer = the root's serial"
run ct "$ISSUER" $BIN/acme-issuer init-update-keys || die "init-update-keys failed"
pause

step "2.3" "Where the keys live"
devices "acme-issuer"
note "root/ and update/ are separate directories, so the keys could live on separate media." \
     "Private keys are 32 bytes (Ed25519 seeds) with mode -rw------- (only root can read)."
run ct "$ISSUER" ls -l /var/lib/acme-issuer/root /var/lib/acme-issuer/update
pause

# =================================================================== PART 3
section "PART 3: PROVISION THE DEVICES (STEPS 0.3 TO 0.6)" "Order matters: trust first, then the server (it holds the registry)"

step "3.1" "Trust: give the station the public certificates"
devices "acme-issuer -> acme-provision"
note "The issuer exports Cert_ACME and both update certificates (no private keys). The" \
     "station verifies the root's self-signature and both update certificates, then" \
     "stores them. Without this, the station can't check the certificates the issuer" \
     "returns, and provisioning stops with 'No trust anchor'."
prov_trust
pause

provision_self() {   # ROLE DEVICE MODEL LABEL
  local role=$1 dev=$2 model=$3 n=$4
  step "$n.a" "Step 0.3 ($role): the $role generates its own keys and request"
  devices "$dev -> acme-provision"
  note "Inside $dev: a random 16-byte serial and an Ed25519 signing key pair are made."
  if [ "$role" = console ]; then
    note "The console also makes an X25519 encryption key pair (enc.key.enc) for Phase 2."
  else
    note "The server makes only a signing key."
  fi
  note "Each private key is encrypted with AES-256-GCM under a key-encryption key derived" \
       "by HKDF from device.secret, a firmware constant, the role and the serial." \
       "request.csr is signed with the new key: proof of possession. The station checks" \
       "that signature and queues the request. Look for: serial=..., the files, and" \
       "the station echoing the same serial."
  prov_keys_self "$role" "$dev" "$model"
  pause
  step "$n.b" "Step 0.4 ($role): the offline issuer signs the certificate"
  devices "acme-provision -> acme-issuer -> acme-provision"
  note "The issuer verifies proof of possession, checks the serial was never issued," \
       "sets validity (10 years, never past the root's expiry) and signs with the root" \
       "key. The station then verifies the certificate against the root and checks it" \
       "matches the request exactly. Look for: SIGNED ..., then VERIFIED ..."
  prov_issue
  pause
  step "$n.c" "Step 0.5 ($role): image assembly"
  devices "acme-provision -> $dev"
  note "The station sends the certificate and Cert_ACME. The device verifies both, checks" \
       "the certificate matches its own request, then decrypts its private key(s) and" \
       "confirms they match the certificate, as the firmware will at every boot."
  [ "$role" = console ] && note "A console also requires both update certificates, with different keys."
  note "Look for: installed serial=... role=$role"
  prov_image "$SERIAL" "$dev"
  pause
  step "$n.d" "Step 0.6 ($role): registration"
  devices "acme-provision -> acme-server"
  note "The server's registry verifies each certificate against its own copy of the root" \
       "and records serial, role, model, status 'active' and timestamps." \
       "'new' = added now; 'known' = already registered with the identical certificate."
  prov_register "$SERIAL"
  pause
}

provision_self server  "$SERVER"  SERVER-1   3.2
provision_self console "$CONSOLE" CONSOLE-X1 3.3

step "3.4.a" "Step 0.3 (cartridge): the STATION generates the cartridge's keys"
devices "acme-provision"
note "Cartridges are too small to generate keys, so the station builds the whole image" \
     "(serial, signing key, device.secret) in its work folder. Cartridges get no" \
     "encryption key and no update certificates. Look for: serial=..."
prov_keys_cart CART-A1
CART_SERIAL=$SERIAL
pause
step "3.4.b" "Step 0.4 (cartridge): the offline issuer signs the certificate"
devices "acme-provision -> acme-issuer -> acme-provision"
note "Same checks as for the server. The station also installs the certificate into its" \
     "working copy of the image and verifies it. Look for: SIGNED, then VERIFIED."
prov_issue
pause
step "3.4.c" "Step 0.5 (cartridge): inject the complete image"
devices "acme-provision -> acme-cartridge"
note "The station sends the WHOLE image (keys and certificates). The cartridge copies" \
     "it, verifies it and unlocks its key; on any failure it wipes what it copied." \
     "Look for: installed serial=... role=cartridge"
prov_image "$CART_SERIAL" "$CARTRIDGE" --role cartridge
pause
step "3.4.d" "Erase the station's copy of the cartridge keys"
devices "acme-provision"
note "Required by the design: the station overwrites each key file with random bytes," \
     "then deletes it. The list names every file it checked, present or not."
run ct "$STATION" $BIN/acme-station erase "$CART_SERIAL" || die "erase failed"
pause
step "3.4.e" "Step 0.6 (cartridge): registration"
devices "acme-provision -> acme-server"
note "The third device is registered: 'new' for the cartridge, 'known' for the update keys."
prov_register "$CART_SERIAL"
pause

step "3.5" "Provisioning result"
devices "acme-server, acme-console, acme-cartridge, acme-provision"
note "Each device is checked the way its firmware will check itself at boot. Look for:" \
     "  state: provisioned, and 'private keys  unlocked, match certificate'" \
     "  console: sign+enc and 'update certs  2'; server and cartridge: sign, 0" \
     "  the same 'trust anchor' serial on every device (the root's)" \
     "  station: three 'issued' serials, none '(keys held)'" \
     "  registry: five 'active' rows (three devices + two update keys)"
status_all
pause
fi   # KEEP

# =================================================================== validation preflight
for c in $SERVER $CONSOLE $CARTRIDGE; do
  ct "$c" test -f /var/lib/acme-device/device.cert || die "$c is not provisioned (run ./demo.sh without --keep)"
done
ct "$STATION" test -f /var/lib/acme-station/trust/root.cert || die "the station has no trust anchor (run ./demo.sh without --keep)"

# =================================================================== PART 4
section "PART 4: VALIDATION, SECTION 1 - DESIGN ATTRIBUTES" "Each step proves one attribute from the design document"

step "4.1" "One trust anchor (offline)"
devices "acme-issuer"
note "Lists the issuer's network interfaces. Only 'lo' (loopback) means it has no" \
     "network at all: the same check the issuer makes before touching its keys."
run ct "$ISSUER" ls /sys/class/net
pause
devices "all five containers"
note "SHA-256 fingerprint of every container's copy of the root certificate." \
     "Five identical hashes = one trust anchor everywhere."
for e in $ISSUER:/var/lib/acme-issuer/root/root.cert $STATION:/var/lib/acme-station/trust/root.cert \
         $SERVER:/var/lib/acme-device/root.cert $CONSOLE:/var/lib/acme-device/root.cert $CARTRIDGE:/var/lib/acme-device/root.cert; do
  show "docker exec ${e%%:*} sha256sum ${e#*:}"; ct "${e%%:*}" sha256sum "${e#*:}"
done
pause
devices "acme-provision, acme-server, acme-console, acme-cartridge"
note "Searches every container except the issuer for the root PRIVATE key." \
     "0 everywhere = the root key exists only on the air-gapped issuer."
for c in $STATION $SERVER $CONSOLE $CARTRIDGE; do
  printf '%-15s %s root.key files\n' "$c:" "$(ct "$c" sh -c 'find /var/lib -name root.key | wc -l')"
done
pause
devices "acme-issuer"
note "Decodes the root certificate: role root, and issuer equal to its own serial" \
     "(self-signed). That serial appears as the issuer on every other certificate."
run ct "$ISSUER" $BIN/acme-issuer show /var/lib/acme-issuer/root/root.cert
pause

step "4.2" "Per-device identities"
devices "acme-server, acme-console, acme-cartridge"
note "Each device's serial, role and public key. All three differ: stealing one key" \
     "compromises one identity, which the server can revoke without affecting others."
for c in $SERVER $CONSOLE $CARTRIDGE; do
  printf '%s== %s%s\n' "$C_STEP" "$c" "$C_OFF"; dstatus "$c" | grep -E 'serial|role|sign_pk'
done
pause
devices "acme-server"
note "Revocation is per serial: the server's genuine certificate is accepted, then the" \
     "same certificate is rejected when a revocation check flags its serial." \
     "('revoked ->' is a label; the second 'revoked' is the error reason.)"
show "python3: verify_cert(server cert), then verify_cert(..., is_revoked=<this serial>)"
ct "$SERVER" python3 -c "
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
pause

step "4.3" "Roles"
devices "acme-cartridge"
note "The cartridge's real, root-signed certificate is checked as a cartridge, a console" \
     "and a server. Only 'cartridge' is accepted: a key extracted from a cheap cartridge" \
     "cannot pose as a console or server (reason: wrong_role)."
show "python3: verify_cert(cartridge cert, expected role = CARTRIDGE, CONSOLE, SERVER)"
ct "$CARTRIDGE" python3 -c "
from acme import cert as C
from acme.cert import Role
anchor = C.load_trust_anchor(open('/var/lib/acme-device/root.cert','rb').read())
raw = open('/var/lib/acme-device/device.cert','rb').read()
for r in (Role.CARTRIDGE, Role.CONSOLE, Role.SERVER):
    try:
        C.verify_cert(raw, anchor, r); print(r.name, 'accepted')
    except C.CertError as e:
        print(r.name, 'rejected:', e)
"
pause
devices "acme-provision"
note "Privileged roles can't even be requested: building a signing request for role" \
     "'update' is refused. Update certificates come only from the offline issuer."
show "python3: csr.make_csr(role=UPDATE)"
ct "$STATION" python3 -c "
from acme import crypto, csr as R
from acme.cert import Role
sk, _ = crypto.sign_keygen()
try:
    R.make_csr(sk, serial=crypto.random(16), role=Role.UPDATE, model='X')
except Exception as e:
    print('refused:', e)
"
pause

step "4.4" "Key separation"
devices "acme-console, acme-server, acme-cartridge"
note "Key files on each device. The console has TWO private keys (sign.key.enc for" \
     "handshakes, enc.key.enc for receiving licenses in Phase 2) plus both update" \
     "certificates. The server and cartridge have one signing key."
for c in $CONSOLE $SERVER $CARTRIDGE; do
  printf '%s== %s%s\n' "$C_STEP" "$c" "$C_OFF"; ct "$c" ls /var/lib/acme-device | grep -E 'key.enc|update'
done
pause
devices "acme-console"
note "The console certificate's two public keys differ (sign_pk vs enc_pk), and both" \
     "private keys decrypt and match them."
dstatus "$CONSOLE" | grep -E 'sign_pk|enc_pk|update certs|private keys'
pause
devices "acme-issuer"
note "The update key is a different key from the root (different sign_pk), kept in its" \
     "own directory: firmware signing never touches the key that mints identities."
show "docker exec $ISSUER $BIN/acme-issuer show root.cert update/primary.cert | grep model|sign_pk"
ct "$ISSUER" $BIN/acme-issuer show /var/lib/acme-issuer/root/root.cert /var/lib/acme-issuer/update/primary.cert | grep -E 'model|sign_pk'
pause

step "4.5" "Software key storage (AES-256-GCM)"
devices "acme-cartridge"
note "The cartridge's image. device.secret (32 bytes) and sign.key.enc are mode 600." \
     "sign.key.enc is 60 bytes: 12-byte nonce + 32-byte encrypted key + 16-byte GCM tag." \
     "The hex dump shows it is unreadable: row 1 starts with the nonce, the last 16" \
     "bytes are the tag. The status line proves the device can still unlock it."
run ct "$CARTRIDGE" ls -l /var/lib/acme-device
run ct "$CARTRIDGE" wc -c /var/lib/acme-device/sign.key.enc
run ct "$CARTRIDGE" od -An -tx1 /var/lib/acme-device/sign.key.enc
dstatus "$CARTRIDGE" | grep 'private keys'
pause
devices "acme-cartridge (on a copy in /tmp/img)"
note "Tamper test: copy the image, flip ONE bit in the last byte of sign.key.enc, then" \
     "check the copy. 'state: provisioned' comes from which files exist; then the" \
     "error shows the GCM tag no longer matches, so the key can't be unlocked."
run ct "$CARTRIDGE" cp -r /var/lib/acme-device /tmp/img
show "python3: flip the lowest bit of the last byte of /tmp/img/sign.key.enc"
ct "$CARTRIDGE" python3 -c "p='/tmp/img/sign.key.enc'; b=bytearray(open(p,'rb').read()); b[-1]^=1; open(p,'wb').write(b)"
expect_fail "tampered key file can't be decrypted" ct "$CARTRIDGE" $BIN/acme-device --home /tmp/img status
ct "$CARTRIDGE" rm -rf /tmp/img
pause
devices "acme-cartridge"
note "Obfuscation, not protection: recompute the key-encryption key from files already" \
     "on the device (HKDF of device.secret, firmware constant, role, serial) and decrypt." \
     "True = whoever controls a device can recover its key. The real defence is" \
     "per-device keys plus server-side detection and revocation."
show "python3: _kek(device.secret, role, serial) -> aead_decrypt(sign.key.enc) -> compare"
ct "$CARTRIDGE" python3 -c "
from pathlib import Path
from acme import keystore as K, crypto, cert as C
d = Path('/var/lib/acme-device')
role = K.DeviceImage(d).role()
cert = C.verify_cert((d/'device.cert').read_bytes(), C.load_trust_anchor((d/'root.cert').read_bytes()), role)
kek = K._kek((d/'device.secret').read_bytes(), role, cert.serial)
sk = crypto.aead_decrypt(kek, (d/'sign.key.enc').read_bytes(), K._aad(cert.serial, 'sign'))
print('recovered key matches certificate:', crypto.sign_public(sk) == cert.sign_pk)
"
pause

step "4.6" "Compact certificate format (CBOR, not X.509)"
devices "acme-cartridge"
note "Raw decode of the cartridge certificate: total size and signature size, then each" \
     "numbered field. 1 version, 2 serial, 3 role (3 = cartridge), 4 model, 5 signing" \
     "key, 7 not_before and 8 not_after (Unix seconds), 9 issuer (the root's serial)." \
     "Field 6, the encryption key, is absent: only consoles have one."
show "python3: cbor2.loads(device.cert) and print each field"
ct "$CARTRIDGE" python3 -c "
import cbor2
raw = open('/var/lib/acme-device/device.cert','rb').read()
tbs, sig = cbor2.loads(raw)
print('total bytes:', len(raw), ' signature bytes:', len(sig))
for k, v in cbor2.loads(tbs).items():
    print(k, v.hex() if isinstance(v, bytes) else v)
"
pause
devices "acme-cartridge"
note "The parser is strict: one byte added or one byte removed and the certificate is" \
     "rejected, because each certificate has exactly one valid encoding."
show "python3: verify_cert(cert + 1 byte), verify_cert(cert - 1 byte)"
ct "$CARTRIDGE" python3 -c "
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
pause

step "4.7" "Modern small algorithms (Ed25519 and X25519)"
devices "acme-console"
note "Key and signature sizes (32 / 64 / 32 bytes). X25519: two fresh key pairs compute" \
     "the same shared secret (True). Ed25519: a genuine signature verifies (True) and" \
     "fails on an altered message (False). Then the library versions installed."
show "python3: sizes, X25519 agreement, Ed25519 verify"
ct "$CONSOLE" python3 -c "
from acme import crypto as c
print('sign_pk', c.SIGN_PK_LEN, 'sig', c.SIG_LEN, 'dh_pk', c.DH_PK_LEN, 'bytes')
a_sk, a_pk = c.dh_keygen(); b_sk, b_pk = c.dh_keygen()
print('X25519 both sides agree:', c.dh(a_sk, b_pk) == c.dh(b_sk, a_pk))
sk, pk = c.sign_keygen(); s = c.sign(sk, b'hi')
print('Ed25519 good/tampered:', c.verify(pk, b'hi', s), c.verify(pk, b'ho', s))
"
ct "$CONSOLE" python3 -c "import nacl, cryptography; print('PyNaCl (libsodium binding)', nacl.__version__, '/ cryptography', cryptography.__version__)"
pause

step "4.8" "Device registry"
devices "acme-server"
note "Every identity ever issued: serial, role, model, status, time registered (UTC)." \
     "Then the same table read directly with sqlite3, and its schema."
run ct "$SERVER" $BIN/acme-registry list
run ct "$SERVER" sqlite3 -header -column /var/lib/acme-server/registry.db "SELECT serial, role, model, status FROM devices;"
run ct "$SERVER" sqlite3 /var/lib/acme-server/registry.db .schema
pause
devices "acme-server"
note "A junk file imported as a certificate is rejected: the registry only accepts" \
     "certificates signed by the root."
ct "$SERVER" sh -c 'mkdir -p /tmp/bad && echo junk > /tmp/bad/x.cert'
expect_fail "junk certificate refused" ct "$SERVER" $BIN/acme-registry import /tmp/bad
ct "$SERVER" rm -rf /tmp/bad
pause

# =================================================================== PART 5
section "PART 5: VALIDATION, SECTION 2 - PROTOCOLS" "Each protocol step again, plus the protections around it"

step "5.1" "Root generation and update keys (offline)"
devices "acme-issuer"
note "Everything the issuer has ever signed, from its append-only log: the root and two" \
     "update keys first, then every device certificate in the order it was signed."
run ct "$ISSUER" $BIN/acme-issuer list
pause
devices "acme-issuer"
note "Running the key generation again is refused: an existing root or update key can" \
     "never be overwritten."
expect_fail "root already exists" ct "$ISSUER" $BIN/acme-issuer init-root
expect_fail "update keys already exist" ct "$ISSUER" $BIN/acme-issuer init-update-keys
pause
devices "a throwaway container WITH a network (deleted afterwards)"
note "The issuer refuses to generate keys when it has a network interface (eth0 here)," \
     "before generating anything."
expect_fail "issuer refuses to run with a network" docker run --rm acme-phase0:latest $BIN/acme-issuer init-root
pause

step "5.2" "Device key generation (in a scratch folder)"
devices "acme-console (scratch folder /tmp/demo; the real identity is untouched)"
note "A demo console generates its own keys. 'state: pending' = keys and a request but" \
     "no certificate. The decoded request has no validity or issuer: those are decided" \
     "by the issuer, never by the device. Its 176 bytes include the device's signature."
ct "$CONSOLE" rm -rf /tmp/demo /tmp/demo-out
run ct "$CONSOLE" $BIN/acme-device --home /tmp/demo init --role console --model DEMO-CONSOLE --csr-out /tmp/demo-out/request.csr
run ct "$CONSOLE" ls -l /tmp/demo
run ct "$CONSOLE" $BIN/acme-device --home /tmp/demo status
run ct "$CONSOLE" $BIN/acme-issuer show /tmp/demo-out/request.csr
pause

step "5.3" "Certificate issuance and duplicate rejection"
devices "acme-console -> acme-issuer"
note "The demo request is streamed to the issuer and signed (it stays in the issuer's" \
     "log as DEMO-CONSOLE). The certificate now has validity and an issuer."
ct "$ISSUER" sh -c "rm -rf /srv/demo-in /srv/demo-out /srv/demo-out2 && mkdir -p /srv/demo-in"
show "docker exec $CONSOLE cat /tmp/demo-out/request.csr | docker exec -i $ISSUER sh -c 'cat > /srv/demo-in/demo.csr'"
ct "$CONSOLE" cat /tmp/demo-out/request.csr | docker exec -i "$ISSUER" sh -c 'cat > /srv/demo-in/demo.csr'
run ct "$ISSUER" $BIN/acme-issuer sign /srv/demo-in /srv/demo-out
show "docker exec $ISSUER $BIN/acme-issuer show /srv/demo-out/*.cert"
ct "$ISSUER" sh -c "$BIN/acme-issuer show /srv/demo-out/*.cert"
pause
devices "acme-issuer"
note "Submitting the same request again is refused: a serial is never issued twice."
expect_fail "serial already issued" ct "$ISSUER" $BIN/acme-issuer sign /srv/demo-in /srv/demo-out2
ct "$CONSOLE" rm -rf /tmp/demo /tmp/demo-out
ct "$ISSUER" rm -rf /srv/demo-in /srv/demo-out /srv/demo-out2
ok "Demo files removed"
pause

step "5.4" "Image assembly and registration: re-provision the cartridge end to end"
devices "acme-cartridge, acme-provision, acme-issuer, acme-server"
note "The cartridge is erased, then steps 0.3 to 0.6 run again as model CART-DEMO:" \
     "station generates keys, issuer signs, station verifies, image injected, station" \
     "erases its copy, server registers. It gets a NEW serial: serials are never reused."
run ct "$CARTRIDGE" $BIN/acme-device erase
prov_keys_cart CART-DEMO; DEMO_SERIAL=$SERIAL
prov_issue
prov_image "$DEMO_SERIAL" "$CARTRIDGE" --role cartridge
run ct "$STATION" $BIN/acme-station erase "$DEMO_SERIAL"
prov_register "$DEMO_SERIAL"
pause
devices "acme-cartridge, acme-console"
note "The new cartridge image (5 files: no encryption key, no update certificates)," \
     "compared with the console's (8 files)."
run ct "$CARTRIDGE" ls -l /var/lib/acme-device
run ct "$CONSOLE" ls -l /var/lib/acme-device
pause
devices "acme-provision"
note "The station's records: every certificate it received, none marked '(keys held)'," \
     "and its work folder is empty: no cartridge keys remain on the station."
run ct "$STATION" $BIN/acme-station list
run ct "$STATION" ls /var/lib/acme-station/work
pause
devices "acme-server"
note "The registry now has a sixth row, CART-DEMO. The old CART-A1 row stays: the" \
     "registry remembers every serial ever issued. Importing again prints 'known'."
run ct "$SERVER" $BIN/acme-registry list
run ct "$SERVER" $BIN/acme-registry import /srv/reg
pause

# =================================================================== PART 6
section "PART 6: VALIDATION, SECTION 3 - IMPLEMENTATION" "The implementation checklist and the unit tests"

step "6.1" "Pinned crypto library"
devices "acme-issuer (same code in every container)"
note "Searches all library code for direct imports of the crypto libraries. Only" \
     "crypto.py: every other module calls its small API (sign, verify, DH, HKDF, AEAD)," \
     "so there is one suite and nothing to negotiate or downgrade."
show "docker exec $ISSUER grep -rlE '^(from|import) (nacl|cryptography)' /opt/acme/acme"
ct "$ISSUER" grep -rlE "^(from|import) (nacl|cryptography)" /opt/acme/acme
pause

step "6.2" "Defined certificate format"
devices "acme-issuer"
note "The header of cert.py documents the wire format; verify_cert() is the single" \
     "function that parses and checks every certificate."
run ct "$ISSUER" sed -n '1,20p' /opt/acme/acme/cert.py
pause

step "6.3" "Offline issuer tool and generated update keys"
devices "acme-issuer, acme-console"
note "The issuer's commands (init-root, init-update-keys, sign, export-public, show," \
     "list). Then the console showing both update keys installed ('update certs  2')."
run ct "$ISSUER" $BIN/acme-issuer --help
dstatus "$CONSOLE" | grep -E 'update certs|private keys'
pause

step "6.4" "Provisioning flow: final state of every device"
devices "acme-server, acme-console, acme-cartridge, acme-provision"
note "All three devices provisioned (the cartridge is now CART-DEMO), the station holds" \
     "no keys, and the registry lists six identities."
status_all
pause

step "6.5" "Unit-tested trust checks"
devices "acme-provision (the tests run inside the container)"
note "The full suite (expect '100 passed'), then only the trust checks by name: wrong" \
     "signer, wrong role, expired, not yet valid, revoked, malformed. In names like" \
     "test_wrong_role[3-2], the numbers are roles: a cartridge (3) presented as a console (2)."
run ct "$STATION" python3 -m pytest -q -p no:cacheprovider
run ct "$STATION" python3 -m pytest tests/test_cert.py -v -p no:cacheprovider \
  -k "wrong_signer or wrong_role or expired or not_yet_valid or revoked or garbage or malformed"
pause

section "DEMO COMPLETE" "Every Phase 0 design attribute, protocol step and checklist item shown"
note "Re-run the validations only:  ./demo.sh --keep" \
     "Start completely fresh:       ./demo.sh" \
     "Save a copy of a run:         ./demo.sh --no-pause 2>&1 | tee demo-output.txt"
