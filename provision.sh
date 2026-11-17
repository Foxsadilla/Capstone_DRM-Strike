#!/usr/bin/env bash
# ===================================================================
# Name: provision.sh
# Nodes: Host
# Purpose: Runs the provisioning flow on the main node
# Notes:
#   - ./provision.sh trust                 give the station Cert_ACME + update certs
#   - ./provision.sh server    MODEL       provision the server      (do this first)
#   - ./provision.sh console   MODEL       provision the console
#   - ./provision.sh cartridge MODEL       provision the cartridge
#   - ./provision.sh status                show every device and the registry
#   - Override container IDs with ISSUER=, STATION=, SERVER=, CONSOLE=, CARTRIDGE=.
#   - Ignore network air-gap by adding: ISSUER_FLAGS=--allow-network
# ===================================================================
set -euo pipefail

ISSUER=${ISSUER:-410}; STATION=${STATION:-411}; SERVER=${SERVER:-412}
CONSOLE=${CONSOLE:-413}; CARTRIDGE=${CARTRIDGE:-414}
ISSUER_FLAGS=${ISSUER_FLAGS:-}
BIN=/opt/acme/bin
TMP=$(mktemp -d)
cleanup() { find "$TMP" -type f -exec shred -u {} + 2>/dev/null || true; rm -rf "$TMP"; }
trap cleanup EXIT

say() { printf '\n== %s\n' "$*"; }
ct()  { local id=$1; shift; pct exec "$id" -- "$@"; }

# carry SRC_ID:SRC_DIR to DST_ID:DST_DIR (replacing DST_DIR)
carry() {
  local src=$1 sdir=$2 dst=$3 ddir=$4
  ct "$src" tar cf /srv/xfer.tar -C "$sdir" .
  pct pull "$src" /srv/xfer.tar "$TMP/xfer.tar"
  ct "$src" shred -u /srv/xfer.tar
  pct push "$dst" "$TMP/xfer.tar" /srv/xfer.tar
  shred -u "$TMP/xfer.tar"
  ct "$dst" sh -c "rm -rf $ddir && mkdir -p $ddir && tar xf /srv/xfer.tar -C $ddir --no-same-owner && shred -u /srv/xfer.tar"
}

serial_of() { sed -n 's/^serial=//p' | tr -d '\r'; }

sign_round() {
  say "Station -> issuer: signing requests (0.4)"
  ct "$STATION" rm -rf /srv/out
  ct "$STATION" $BIN/acme-station export-requests /srv/out
  carry "$STATION" /srv/out "$ISSUER" /srv/inbox
  ct "$ISSUER" rm -rf /srv/outbox
  ct "$ISSUER" $BIN/acme-issuer $ISSUER_FLAGS sign /srv/inbox /srv/outbox
  say "Issuer -> station: certificates"
  carry "$ISSUER" /srv/outbox "$STATION" /srv/in
  ct "$STATION" $BIN/acme-station receive /srv/in
}

deliver() {   # deliver SERIAL DEVICE_ID [install args]
  local serial=$1 dev=$2; shift 2
  say "Station -> device $dev: image assembly (0.5)"
  ct "$STATION" rm -rf /srv/out
  ct "$STATION" $BIN/acme-station export "$serial" /srv/out
  carry "$STATION" /srv/out "$dev" /srv/in
  ct "$STATION" $BIN/acme-station wipe-dir /srv/out
  ct "$dev" $BIN/acme-device install /srv/in "$@"
  ct "$dev" $BIN/acme-station wipe-dir /srv/in
}

register() {  # register SERIAL
  say "Registration on the server (0.6)"
  ct "$STATION" rm -rf /srv/reg
  ct "$STATION" sh -c "mkdir -p /srv/reg && cp /var/lib/acme-station/certs/$1.cert /var/lib/acme-station/trust/update-*.cert /srv/reg/"
  carry "$STATION" /srv/reg "$SERVER" /srv/reg
  ct "$SERVER" $BIN/acme-registry import /srv/reg
}

self_keyed() {  # self_keyed ROLE DEVICE_ID MODEL   (console, server)
  local role=$1 dev=$2 model=$3 serial
  say "Device $dev generates its own keys (0.3)"
  ct "$dev" rm -rf /srv/out
  serial=$(ct "$dev" $BIN/acme-device init --role "$role" --model "$model" --csr-out /srv/out/request.csr | serial_of)
  [ -n "$serial" ] || { echo "key generation failed" >&2; exit 1; }
  echo "serial $serial"
  carry "$dev" /srv/out "$STATION" /srv/in
  ct "$STATION" $BIN/acme-station accept /srv/in/request.csr
  sign_round
  deliver "$serial" "$dev"
  register "$serial"
}

case "${1:-}" in
  trust)
    say "Issuer -> station: public certificates"
    ct "$ISSUER" rm -rf /srv/public
    ct "$ISSUER" $BIN/acme-issuer export-public /srv/public
    carry "$ISSUER" /srv/public "$STATION" /srv/trust
    ct "$STATION" $BIN/acme-station trust /srv/trust ;;
  server)   self_keyed server  "$SERVER"  "${2:?model required}" ;;
  console)  self_keyed console "$CONSOLE" "${2:?model required}" ;;
  cartridge)
    model=${2:?model required}
    say "Station generates the cartridge keys (0.3)"
    serial=$(ct "$STATION" $BIN/acme-station new-cartridge --model "$model" | serial_of)
    [ -n "$serial" ] || { echo "key generation failed" >&2; exit 1; }
    echo "serial $serial"
    sign_round
    deliver "$serial" "$CARTRIDGE" --role cartridge
    say "Station erases its copy of the cartridge keys"
    ct "$STATION" $BIN/acme-station erase "$serial"
    register "$serial" ;;
  status)
    for dev in "$SERVER" "$CONSOLE" "$CARTRIDGE"; do
      say "Device $dev"; ct "$dev" $BIN/acme-device status || true
    done
    say "Station";  ct "$STATION" $BIN/acme-station list || true
    say "Registry"; ct "$SERVER" $BIN/acme-registry list || true ;;
  *) sed -n '2,12p' "$0"; exit 1 ;;
esac