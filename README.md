# DRM-Strike Phase-0
## Phase Goals
### Section 1 - Design Attributes
- [ ] One Trust Anchor (Offline)
- [ ] Per-Device Identities
- [ ] Roles
- [ ] Key Seperation
- [ ] Software Key Storage (ES-256-GCM)
- [ ] Compact Certificate Format (Serial, Role, Model, PK, Validity, Issuer Signature)
- [ ] Modern Small Algorithms (Ed25519 and X25519)
- [ ] Device Registry (Serial, Role, Model, and Status)
### Section 2 - Protocols
- [ ] Root Generattion (Offline)
- [ ] Update Keys (Offline)
- [ ] Device Key Generation
- [ ] Cert Issuance
- [ ] Image Assembly
- [ ] Registration
### Section 3 - Implementations
- [ ] Pinned Crypto Library
- [ ] Defined Cert Format
- [ ] Offline Issuer Tool
- [ ] Generated Update Keys
- [ ] Software Key Storage
- [ ] Provisioning Flow
- [ ] Device Registry
- [ ] Unit-Tested the Trust Checks

## Containers

| CT             | Role                                          |
| -------------- | --------------------------------------------- |
| acme-isser     | issues ACME key and updates keys              |
| acme-provision | Manufacture Sim and provisioning              |
| acme-server    | Server identity and device registry           |
| acme-console   | Console identity; signing and encryption keys |
| acme-cartridge | cartridge identity; signing key only          |
## Notes
### Definitions
- **HMAC-based Key Derivation Function (HKDF)**: Defined in RFC 5869, it is a cryptographic standard used to derive one or more strong, independent keys from shared secret material (*Python:* `hkdf()`).
	- **Hash-based Message Authentication Code (HMAC)**:  It is a cryptographic technique that combines a secret key with a hash function (such as SHA-256) to verify both the data integrity and authenticity of a message.
	- **HKDF-SHA256**: HKDF using the SHA-256 cryptographic hash function to derive strong, fixed- or variable-length secret keys from initial keying material.
- **Diffie-Hellman (DH)**: a cryptographic method that lets two parties safely generate a shared secret key over an insecure public network without ever transmitting the key itself (*Python*: `dh()`).
- **X25519**: An *elliptic-curve Diffie-Hellman (ECDH)* key exchange function that uses the curve25519 elliptic curve and 32-byte keys to let two parties establish a shared secret over an insecure channel.
- **Advanced Encryption Standard in Galois/Counter Mode (AES-GCM)**: 
	- *AES* - A trusted symmetric-key block cipher that locks and unlocks data using 128, 192, or 256 bit secret keys.
	- *GCM* - A mdoe of operation that turns AES into a fast stream cipher (counter mode) while adding a universal hashing function (Galois/GHASH) over a binary finite field to generate an authentication tag.
	- **AES-256-GCM**: using a 256-bit key to provide both confidentiality and data integrity. Encrypts data while generating an authentication tag to detect tampering
- **To-be-Signed (TBS)**: Data, a message, or a certificate has a digital signature attached to verify its origin and integrity
- **Binary Large Object (Blob)**: An opaque block of raw bytes (e.g., crypto key, encrypted payload, or large data packet) treated without structural parsing by the storage or transport layer.
- **Concise Binary Object Representation (CBOR):** A binary data serialization format designed to be small, fast to process, and schema free while sharing a data model similar to JSON.
### Procedures
- **How does Phase 0 devices encrypt traffic?**
	- The main purpose of phase 0 is to create and setup the keys and certs that will be used for the encryption of the traffic sent during the future phases.
	- The encrypted session of these future phases will be using: `X25519 + HKDF + AES-GCM`
#### Process of Sign, Agree, Derive, & Seal
- The main process of: sign, agree, derive, and seal, is done within the `crytpo.py` file so the other files do not need to import the crypto library.
	- **Sign**: Using the Ed25519 Algorithm, proves who made something
	- **Agree**: Using the X25519 Algorithm, two parties make a shared secret
	- **Derive**: Using the HKDF-SHA256 Algorithm, turns a secret into a proper key
	- **Seal**: Using the AES-256-GCM Algorithm, encrypts and detects tampering
- **Step 1: Sign**
	- Using Ed25519, a **private key (SK)** makes a 64-byte signature and anyone holding the 32 byte **public key (PK)** can check it.
		- *Note,* in phase 0, secret key != SK, for clarification. private and secret keys aren't the same thing.
	- The purpose of this is that the signatures give authenticity, not secrecy. A cert is not a secret; what matters is only the official ACME could have made this.
	- In `csr.py` the device will sign its own request with its new key for **proof of possession**, the device is proving it actually holds the SK matching the PK it wants certified.
	- *Code Example:*
``` python
# cert.py, issue_cert(): ACME signs a certificate
sig = crypto.sign(issuer_sk, SIG_CONTEXT + tbs)

# cert.py, verify_cert(): a device checks it against the root's public key
if not crypto.verify(anchor.sign_pk, SIG_CONTEXT + tbs_bytes, sig):
    raise CertError("bad_signature")
```
- **Step 2: Agree**
	- Using X25519, each side combines its private key with the other side's PK, and both get the same 32-byte secret. Nobody watching the PK can compute this.
	- This lets two devices create a share encryption key without sending the key
	- This exists in `crypto.dh()` but is not in used in Phase 0 yet because nothing calls it yet. Only the console gets an X25519 key par (`enc_pk` in its cert), because it'll eventually encrypt licenses to the console.
	- It uses an all zero check to block any malicious low order PK that would force a predictable secret. The result must always go through `hkdf()`, because a raw DH output isn’t a uniformly random key.
	- *Code Example:*
``` python
# crypto.py: the safety checks
if shared == bytes(32):
    raise CryptoError(f"{ECDH_Key} produced an all-zero secret!")
```
- **Step 3: Derive**
	- Using HKDF-SHA256, takes **input key material (IKM)**, a salt and an info label, and outputs a strong key
	- The info label is used to bind the key to one purpose and one device, so the same secret cannot produce interchangeable keys
	- This happens in `keystore.kek()` where it builds the **key-encryption key (KEK)**
	- *Code Example:*
``` python
crypto.hkdf(secret, FIRMWARE_CONSTANT, b"ACME-KEK-v1" + bytes([int(role)]) + serial)
#           ^ikm     ^salt              ^info: version + role + this device's serial
```
- **Step 4: Seal**
	- Using AES-256-GCM, authenticated encryption happens. Each call uses a fresh random 12-byte nonce and outputs: `nonce || ciphertext || 16-byte tag`. If one bit changes the decryption will fail.
	- This will provide confidentiality and integrity with extra **AAD (Additional Associated Data)** that isn't encrypted but is checked which ties a cipher text to its context so that an attacker cannot take a valid ciphertext and move, replay, or re-assign it somewhere else.
	- `_aad(serial, "sign")` is used to mean a sign-key blob cannot be swapped with the enc-key blob or copied to another device (There is a test for this).
	- The `keystore.create()` encrypts private keys before writing them to the disk:
``` python
_write(self._p("sign.key.enc"), crypto.aead_encrypt(kek, sign_sk, _aad(serial, "sign")), 0o600)
```
#### Key Storage
- At the boot, the `load()` repeats the following backwards, decrypts, and checks the decrypted key matches the cert (`sign_public(sign_sk) != cert.sign_pk`)
```
device.secret (32 random bytes) ─┐
FIRMWARE_CONSTANT (in code) ─────┼─ HKDF ─▶ KEK ─ AES-256-GCM ─▶ sign.key.enc
role + serial ───────────────────┘                    (aad: serial + "sign")
```
- The purpose of this is obfuscation, not protection. Both inputs to the KEK are on the device so anyone who controls the device can recompute it. The design relies instead on unique per-device keys + server-side detection and revocation, where stealing one key gives you one identity which the server can ban.
#### Device Trust
- *Uses “Form, Signer, Role, Time, Revoked”:*
	- **Form:** Valid CBOR, correct fields (`_split,`, `_check_fields`)
	- **Signer:** Signed by the ACME root, with matching serial
	- **Role:** The role is the one expected (mandatory argument)
	- **Time:** Inside `not_before` - `not_after`
	- **Revoked:** Not on the revocation list
#### Design Attributes
- One trust anchor (ACME Root)
	- Simple verification, only on catastrophic key and it is kept offline
- Per-device keys
	- One extraction for one revocable identity, not all devices
- Roles in certs
	- Stolen keys cannot be used to spoof as a console or server
- Separate sign and encrypt keys on the console
	- Reusing one key for two purposes has the potential for cross-protocol attacks
- Update key separate from issuing key
	- Firmware signing will never touch that key that mints the identities
- Backup update key
	- Recovery path if the primary update key gets leaked
- Context strings (e.g., "`ACME-CERT-v1", "ACME-CSR-v1"`)
	- A signature made for one purpose cannot be reused as another
- CBOR instead of alternative (e.g., X.509)
	- Simple for a cartridge chip
- Ed25519/X25519
	- Makes small keys. constant time code and has no parameters to get wrong
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
### 1. Setup
``` bash
cd <PATH>
chmod +x provision.sh bin/*

cd docker

docker compose up -d --build
docker compose ps

# Should be 100 passed
docker exec acme-provision python3 -m pytest -q
cd ..
```
### 2. Trust Anchors
Phase 0's steps 0.1-0.2
``` bash
docker exec acme-issuer /opt/acme/bin/acme-issuer init-root
docker exec acme-issuer /opt/acme/bin/acme-issuer init-update-keys
docker exec acme-issuer /opt/acme/bin/acme-issuer list
```

### 3. Provision Devices
Phase 0's steps 0.3-0.6
**0.3 - Keys**
- The console and servers keys are generated on their own device and they write a signing request
- The cartridge has its keys generated by the station
**0.4 - Issuance**
- The console, cartridge, and server requests go through the station then to the issuer. The station verifies the returned cert
**0.5 - Image**
- Console and Server receives the cert, the ACME cert and update the certificates
- The cartridge has the station send the complete image and then erases its copy of the keys 
**0.6 - Registry**
- The server verifies the cert and records the serial, role, model, status active, and timestamps
``` bash
export RUNTIME=docker
./provision.sh server    SERVER-1
./provision.sh console   CONSOLE-X1
./provision.sh cartridge CART-A1
./provision.sh status
```

### 4. Commands

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
### 5. Notes

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

...