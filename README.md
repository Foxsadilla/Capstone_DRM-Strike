# DRM-Strike Phase-0
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
- **X25519**: An elliptic-curve Diffie-Hellman (ECDH) key exchange function that uses the curve25519 elliptic curve and 32-byte keys to let two parties establish a shared secret over an insecure channel.
- **Advanced Encryption Standard in Galois/Counter Mode (AES-GCM)**: 
	- *AES* - A trusted symmetric-key block cipher that locks and unlocks data using 128, 192, or 256 bit secret keys.
	- *GCM* - A mdoe of operation that turns AES into a fast stream cipher (counter mode) while adding a universal hashing function (Galois/GHASH) over a binary finite field to generate an authentication tag.
	- **AES-256-GCM**: using a 256-bit key to provide both confidentiality and data integrity. Encrypts data while generating an authentication tag to detect tampering
- **To-be-Signed (TBS)**: Data, a message, or a certificate has a digital signature attached to verify its origin and integrity
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
- **Step 1**
	- Using Ed25519, a **private key (SK)** makes a 64-byte signature and anyone holding the 32 byte **public key (PK)** can check it.
		- *Note,* in phase 0, secret key != SK, for clarification. private and secret keys aren't the same thing.
	- The purpose of this is that the signatures give authenticity, not secrecy. A cert is not a secret; what matters is only the official ACME could have made this.
``` python
# cert.py, issue_cert(): ACME signs a certificate
sig = crypto.sign(issuer_sk, SIG_CONTEXT + tbs)

# cert.py, verify_cert(): a device checks it against the root's public key
if not crypto.verify(anchor.sign_pk, SIG_CONTEXT + tbs_bytes, sig):
    raise CertError("bad_signature")
```


## Files
### Host View
```
├── acme
│   ├── cert.py
│   ├── crypto.py
│   ├── csr.py
│   ├── device.py
│   ├── __init__.py
│   ├── issuer.py
│   ├── keystore.py
│   ├── registry.py
│   └── station.py
├── bin
│   ├── acme-device
│   ├── acme-issuer
│   ├── acme-registry
│   └── acme-station
├── docker
│   ├── .env
│   ├── acme-phase0-lib.tar.gz
│   ├── Cartridge.yaml
│   ├── Console.yaml
│   ├── Dockerfile
│   ├── Issuer.yaml
│   ├── Provision.yaml
│   └── Server.yaml
├── provision.sh
├── README.md
└── tests
    ├── test_cert.py
    ├── test_crypto.py
    └── test_issuer.py

5 directories, 25 files
```

### Container View

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
./provision.sh trust
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

#### Certificate Format

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
