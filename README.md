# DRM-Strike Phase-0
## Phase Goals
### Section 1 - Design Attributes
- [x] One Trust Anchor (Offline)
- [x] Per-Device Identities
- [x] Roles
- [x] Key Seperation
- [x] Software Key Storage (ES-256-GCM)
- [x] Compact Certificate Format (Serial, Role, Model, PK, Validity, Issuer Signature)
- [x] Modern Small Algorithms (Ed25519 and X25519)
- [x] Device Registry (Serial, Role, Model, and Status)
### Section 2 - Protocols
- [x] Root Generattion (Offline)
- [x] Update Keys (Offline)
- [x] Device Key Generation
- [x] Cert Issuance
- [x] Image Assembly
- [x] Registration
### Section 3 - Implementations
- [x] Pinned Crypto Library
- [x] Defined Cert Format
- [x] Offline Issuer Tool
- [x] Generated Update Keys
- [x] Software Key Storage
- [x] Provisioning Flow
- [x] Device Registry
- [x] Unit-Tested the Trust Checks

## Containers

| CT             | Role                                          |
| -------------- | --------------------------------------------- |
| acme-isser     | issues ACME key and updates keys              |
| acme-provision | Manufacture Sim and provisioning              |
| acme-server    | Server identity and device registry           |
| acme-console   | Console identity; signing and encryption keys |
| acme-cartridge | cartridge identity; signing key only          |

## Files

| Path                               | Contents                                                 | Storage                |
| ---------------------------------- | -------------------------------------------------------- | ---------------------- |
| `/opt/acme`                        | Code in this and subdirectories                          | In image               |
| `/var/lib/acme-issuer`             | Issuer only with root key, update keys, and issuance log | Volume issuer-data     |
| `/var/lib/acme-station`            | Station only with trust cert, requests, and issued certs | Volume station-data    |
| `/var/lib/acme-device`             | server, console, and cartridge, the device image         | volume \*-identity*    |
| `/var/lib/acme-server/registry.db` | server only, device registry with SQLite                 | volume server-registry |
| `/srv`                             | Transfer folders by `provision.sh`                       | container filesystem   |
## Run Docker

### 1. Prerequisites`
 
| Step | What it does                              | Phase 0 steps |
| ---- | ----------------------------------------- | ------------- |
| 1    | Check the prerequisites                   |               |
| 2    | Build the image and start the containers  |               |
| 3    | Run the unit tests                        |               |
| 4    | Create the root and update keys           | 0.1-0.2       |
| 5    | Provision the server, console, cartridge  | 0.3-0.6       |
| 6    | Run the Phase 0 validations               | All           |
 
To run steps 2 to 6 in one go, see [One command](#one-command).
 
### 1. Prerequisites
- Docker Engine with the Compose plugin: `docker compose version` should print a version.
- Your user in the `docker` group, so no `sudo` is needed: `groups` should list `docker`. If not, run `sudo usermod -aG docker $USER`, then log out and back in.
- Unix (LF) line endings on every script. A copy edited or checked out on Windows can have Windows (CRLF) endings, which break the scripts with errors like `set: pipefail: invalid option name` or `/usr/bin/env: 'python3\r'`. The repo's `.gitattributes` prevents this for Git checkouts; to fix a copy by hand:
``` bash
sed -i 's/\r$//' provision.sh demo.sh docker/*.sh bin/*
chmod +x provision.sh demo.sh docker/*.sh bin/*
```
 
### 2. Build and Start
``` bash
cd docker
docker compose down -v     
docker compose up -d --build
docker compose ps          
cd ..
```

### 3. Unit Tests
``` bash
docker exec acme-provision python3 -m pytest -q
```
Expected: `100 passed`. 
 
### 4. Trust Anchor
Phase 0's steps 0.1-0.2, run inside the air-gapped issuer:
``` bash
docker exec acme-issuer /opt/acme/bin/acme-issuer init-root
docker exec acme-issuer /opt/acme/bin/acme-issuer init-update-keys
docker exec acme-issuer /opt/acme/bin/acme-issuer list
```
 
### 5. Provision Devices
Phase 0's steps 0.3-0.6:
``` bash
./provision.sh trust                  # Station receives the root and update certificates (run first)
./provision.sh server    SERVER-1     # Server before the others: it holds the registry
./provision.sh console   CONSOLE-X1
./provision.sh cartridge CART-A1
./provision.sh status
```
Each device run prints a heading for each step:
 
**0.3 - Keys**
- The server and console generate their own keys and write a signing request
- The station generates the cartridge's keys, since cartridges are too small to do it
**0.4 - Issuance**
- Requests go from the station to the issuer, which signs them; the station verifies each returned certificate against the root
**0.5 - Image**
- The server and console receive their certificate and the root certificate; the console also keeps both update certificates
- The cartridge receives its complete image, then the station erases its copy of the keys
**0.6 - Registry**
- The server verifies each certificate and records the serial, role, model, status `active` and timestamps
Expected from `status`:
- All three devices show `state: provisioned` and `private keys  unlocked, match certificate`
- The console shows `sign+enc` and `update certs  2`; the server and cartridge show `sign` and `update certs  0`
- The station lists three `issued` serials, none marked `(keys held)`
- The registry lists five `active` rows: the three devices and the two update keys
Files move between containers as a tar stream piped through the host, standing in for removable media. No file passes through the host's disk, so the containers never see files owned by your user.
 
### 6. Validations
``` bash
cd docker
./phase0-validations.sh 2>&1 | tee ../validation-output.txt
cd ..
```
The script checks every item in [Phase Goals](#phase-goals) and prints a heading for each. It stops early with `FATAL` if a device or the station isn't provisioned.
 
It also erases and re-provisions the cartridge as `CART-DEMO`, so afterwards the registry has a sixth row and the cartridge's model is `CART-DEMO`.
 
Some checks are meant to fail, to prove a protection works. These results are expected:
 
| Output                                          | What it proves                                          |
| ----------------------------------------------- | ------------------------------------------------------- |
| `REJECTED x.cert: malformed` and `exit=1`       | The registry refuses a file that isn't a certificate    |
| `Root already exists` and `exit=2`              | The root key can't be overwritten                       |
| `Update kesy already exist` and `exit=2`        | The update keys can't be overwritten                    |
| `Network interfece(s) currently present: eth0`  | The issuer refuses to run with a network                |
| `REJECTED demo.csr: ... already issued`         | The issuer never reuses a serial                        |
| `error: cannot unlock private key`              | A one-bit change to a key file is detected (tamper test) |
 
The messages in the first column go to standard error. Keep `2>&1` when saving the output, or the file will show only the `exit=` codes.
 
### One Command
`test-setup.sh`, in the project folder, runs steps 2 to 6 from a clean start:
``` bash
./demo.sh 2>&1 | tee output.txt
```
- It runs `docker compose down -v` first, so it **deletes the root key and every identity** each time.
- It expects the project at `~/Documents/Capstone_DRM-Strike`. To use another folder, change `PROJECT_DIR` at the top of the script.
### Start Over
``` bash
cd docker
docker compose down -v
docker compose up -d --build
cd ..
```
Then repeat steps 4 to 6. `down -v` deletes the volumes, so a new root and new identities are created.

### Commands

| Task                 | Commnd                                                                                                                                                                                   |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Inspect Cert/Request | `docker exec acme-issuer /opt/acme/bin/acme-issuer show <file>`                                                                                                                          |
| Check one device     | `docker exec acme-console /opt/acme/bin/acme-device status`                                                                                                                              |
| List the registry    | `docker exec acme-server /opt/acme/bin/acme-registry list`                                                                                                                               |
| Redo one device      | `docker exec <container> /opt/acme/bin/acme-device erase`, then provision again (a new serial is issued; the old one stays in the registry)                                              |
| Second cartridge     | Copy `cartridge.yaml` to `cartridge2.yaml`, change the service, `container_name` and volume to `cartridge2`, start it, then `CARTRIDGE=acme-cartridge2 ./provision.sh cartridge CART-A1` |
| Update the code      | `docker compose up -d --build` in `docker/`                                                                                                                                              |
| Stop                 | `docker compose down`                                                                                                                                                                    |
| Kill instance        | `docker compose down -v`                                                                                                                                                                 |
### Details

#### Certificate Format (CBOR)

| Key | Field        | Type                                                                 |
| --- | ------------ | -------------------------------------------------------------------- |
| 1   | Version      | Int                                                                  |
| 2   | Serial       | 16-bytes                                                             |
| 3   | Role         | 0 - root<br>1 - server<br>2 - console<br>3 - cartridge<br>4 - update |
| 4   | Model        | Text (1-32 char)                                                     |
| 5   | Signing PK   | 32 bytes (Ed25519)                                                   |
| 6   | Encrypted PK | 32 bytes (X25519), consoles only                                     |
| 7   | Not Before   | Unix Sec                                                             |
| 8   | Not After    | Unix Sec                                                             |
| 9   | Ussuer       | 16-byte  serial of issuer cert                                       |

**Certificate in CBOR Diagnostic Notation:**
``` cbor-diag
{
  1: 1,                                  / Version (Int) /
  2: h'00112233445566778899AABBCCDDEEFF', / Serial (16-byte bstr) /
  3: 2,                                  / Role: 2 = console (Int) /
  4: "Model-X1",                         / Model (tstr, 1-32 chars) /
  5: h'A1B2C3...32_BYTES_ED25519...',    / Signing PK (32-byte bstr) /
  6: h'D4E5F6...32_BYTES_X25519...',     / Encrypted PK (32-byte bstr) /
  7: 1735689600,                         / Not Before (Unix Sec Int) /
  8: 1767225600,                         / Not After (Unix Sec Int) /
  9: h'FFEEDDCCBBAA99887766554433221100'  / Issuer Serial (16-byte bstr) /
}
```