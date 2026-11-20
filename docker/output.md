> Navigating to docker directory and resetting containers...
 Container acme-console Stopping 
 Container acme-issuer Stopping 
 Container acme-cartridge Stopping 
 Container acme-provision Stopping 
 Container acme-server Stopping 
 Container acme-issuer Stopped 
 Container acme-issuer Removing 
 Container acme-provision Stopped 
 Container acme-provision Removing 
 Container acme-cartridge Stopped 
 Container acme-cartridge Removing 
 Container acme-cartridge Removed 
 Container acme-provision Removed 
 Container acme-issuer Removed 
 Container acme-server Stopped 
 Container acme-server Removing 
 Container acme-console Stopped 
 Container acme-console Removing 
 Container acme-server Removed 
 Container acme-console Removed 
 Volume acme-phase0_issuer-data Removing 
 Network acme-net Removing 
 Volume acme-phase0_console-identity Removing 
 Volume acme-phase0_server-registry Removing 
 Volume acme-phase0_server-registry Removed 
 Volume acme-phase0_server-identity Removing 
 Volume acme-phase0_cartridge-identity Removing 
 Volume acme-phase0_station-data Removing 
 Volume acme-phase0_issuer-data Removed 
 Volume acme-phase0_cartridge-identity Removed 
 Volume acme-phase0_console-identity Removed 
 Volume acme-phase0_station-data Removed 
 Volume acme-phase0_server-identity Removed 
 Network acme-net Removed 
 Image acme-phase0:latest Building 
 Image acme-phase0:latest Building 
 Image acme-phase0:latest Building 
 Image acme-phase0:latest Building 
 Image acme-phase0:latest Building 
#1 [internal] load local bake definitions
#1 reading from stdin 2.41kB done
#1 DONE 0.0s

#2 [server internal] load build definition from Dockerfile
#2 transferring dockerfile: 581B done
#2 DONE 0.0s

#3 [console internal] load metadata for docker.io/library/debian:trixie-slim
#3 DONE 0.3s

#4 [cartridge internal] load .dockerignore
#4 transferring context: 2B done
#4 DONE 0.0s

#5 [cartridge 1/7] FROM docker.io/library/debian:trixie-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2
#5 resolve docker.io/library/debian:trixie-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2 0.0s done
#5 DONE 0.0s

#6 [cartridge internal] load build context
#6 transferring context: 688B done
#6 DONE 0.0s

#7 [provision 5/7] COPY tests /opt/acme/tests
#7 CACHED

#8 [provision 3/7] COPY acme  /opt/acme/acme
#8 CACHED

#9 [provision 4/7] COPY bin   /opt/acme/bin
#9 CACHED

#10 [provision 2/7] RUN apt-get update  && apt-get install -y --no-install-recommends       python3 python3-nacl python3-cryptography python3-cbor2       python3-pytest sqlite3  && rm -rf /var/lib/apt/lists/*
#10 CACHED

#11 [provision 6/7] RUN chmod 755 /opt/acme/bin/* && mkdir -p /srv
#11 CACHED

#12 [cartridge 7/7] WORKDIR /opt/acme
#12 CACHED

#13 [cartridge] exporting to image
#13 exporting layers done
#13 exporting manifest sha256:987416723318032723bdfdfdfc5c3922713e087e8d92d3cc85a6e385557e5ffb done
#13 exporting config sha256:6698fd03ec4e4f826954b332c161499280c3f5573d328c36a6ca005192dffdaf done
#13 exporting attestation manifest sha256:fd2f2da2dd03088b56c83651ef20360f0c014c3bfb4eeb4ed719231a6d4be302 0.0s done
#13 exporting manifest list sha256:d172fec97729c7e082cd38937fdbf560e532ff3d9011ac2e98da3dcd4c966e32
#13 exporting manifest list sha256:d172fec97729c7e082cd38937fdbf560e532ff3d9011ac2e98da3dcd4c966e32 0.0s done
#13 naming to docker.io/library/acme-phase0:latest done
#13 unpacking to docker.io/library/acme-phase0:latest 0.0s done
#13 DONE 0.1s

#14 [issuer] exporting to image
#14 exporting layers done
#14 exporting manifest sha256:87d6e9dff501982de1a6fa0f1b978168c3b5d14e1fbf6329ce63f10e8c1fc11c done
#14 exporting config sha256:edacfc2d4359e6debf776dd0f2a730461daf7e054b926b8fe428c03daf487fda done
#14 exporting attestation manifest sha256:2c6797cf315632145d6c3638a693a1e5f5f1922546e780fdfaad6e86d1e62070 0.0s done
#14 exporting manifest list sha256:ae7f1c1d4146185b1c97706f883950be0b2b57b3a9a7b69de51de13665b2c014 0.0s done
#14 naming to docker.io/library/acme-phase0:latest done
#14 unpacking to docker.io/library/acme-phase0:latest 0.0s done
#14 DONE 0.1s

#15 [provision] exporting to image
#15 exporting layers done
#15 exporting manifest sha256:fbdcd78c6ea47c4b87e259d0626c097281ed6e884ef12189dc755d2132129b50 done
#15 exporting config sha256:5044ece6aab0a26439559bc1b43e0f160539654d9fa00fc6d893d2a2e7a73f93 0.0s done
#15 exporting attestation manifest sha256:063fdb49745de5ce1370271189c664c13c1aec9e80a7b8913a1d6106ba5a8ccd 0.0s done
#15 exporting manifest list sha256:49238fa5932554c2729a9a4a2c93a2c6e697818d6eff63260fc7640c9711512f 0.0s done
#15 naming to docker.io/library/acme-phase0:latest done
#15 unpacking to docker.io/library/acme-phase0:latest done
#15 DONE 0.1s

#16 [server] exporting to image
#16 exporting layers done
#16 exporting manifest sha256:b9dd8df8bdbbba608c8442740170e142ce8a5177f2bdf242db89fa5506178634 done
#16 exporting config sha256:cfca1e870ae8caf542a85a52868ddabfeb3364255069822981a594414eeec2cb 0.0s done
#16 exporting attestation manifest sha256:cc03eb5a2a9322b82b961e6edb3fed5bf0b6ae307666f5973e431a744a79255d 0.0s done
#16 exporting manifest list sha256:bed8ddb474bd6ef5030cca4530c46d120fdb30e12a067244a0521ea87fcbc116 0.0s done
#16 naming to docker.io/library/acme-phase0:latest done
#16 unpacking to docker.io/library/acme-phase0:latest done
#16 DONE 0.1s

#17 [console] exporting to image
#17 exporting layers done
#17 exporting manifest sha256:eded8befde8a46c44979758ea1a14b1aadda604f0de018ee95981aa707098afd done
#17 exporting config sha256:bf58e162ecec8b7bb9ddccfbb3464d0be485722ede5e0e1662336e01608826f4 0.0s done
#17 exporting attestation manifest sha256:81d40e026e15e9e28e605bcd6375a100215a75f8d7b461c031d0576d13365595 0.0s done
#17 exporting manifest list sha256:7e34c68d4e3b309edd383859f1b67e82ea796048d86bbeed6090020d095861e5 0.0s done
#17 naming to docker.io/library/acme-phase0:latest done
#17 unpacking to docker.io/library/acme-phase0:latest done
#17 DONE 0.1s

#18 [issuer] resolving provenance for metadata file
#18 DONE 0.1s

#19 [server] resolving provenance for metadata file
#19 DONE 0.1s

#20 [cartridge] resolving provenance for metadata file
#20 DONE 0.1s

#21 [provision] resolving provenance for metadata file
#21 DONE 0.0s

#22 [console] resolving provenance for metadata file
#22 DONE 0.0s
 Image acme-phase0:latest Built 
 Image acme-phase0:latest Built 
 Image acme-phase0:latest Built 
 Image acme-phase0:latest Built 
 Image acme-phase0:latest Built 
 Volume acme-phase0_server-registry Creating 
 Volume acme-phase0_issuer-data Creating 
 Volume acme-phase0_station-data Creating 
 Network acme-net Creating 
 Volume acme-phase0_console-identity Creating 
 Volume acme-phase0_server-identity Creating 
 Volume acme-phase0_cartridge-identity Creating 
 Volume acme-phase0_issuer-data Created 
 Container acme-issuer Creating 
 Volume acme-phase0_console-identity Created 
 Volume acme-phase0_server-registry Created 
 Volume acme-phase0_server-identity Created 
 Volume acme-phase0_cartridge-identity Created 
 Container acme-cartridge Creating 
 Volume acme-phase0_station-data Created 
 Container acme-provision Creating 
 Network acme-net Created 
 Container acme-server Creating 
 Container acme-console Creating 
 Container acme-issuer Created 
 Container acme-provision Created 
 Container acme-cartridge Created 
 Container acme-server Created 
 Container acme-console Created 
 Container acme-server Starting 
 Container acme-console Starting 
 Container acme-cartridge Starting 
 Container acme-issuer Starting 
 Container acme-provision Starting 
 Container acme-server Started 
 Container acme-console Started 
 Container acme-cartridge Started 
 Container acme-issuer Started 
 Container acme-provision Started 
> Initializing ACME issuer keys...
Root created: /var/lib/acme-issuer/root/root.cert
 type        certificate
 bytes       168
 serial      ac8d20719c099758def8e7d932b19cde
 role        root
 model       ACME-ROOT
 sign_pk     d0d49b65a2da2d687342e9881aee5546e805a132df0ecfdfb2d47688c8e2ac42
 not_before  2026-11-20 04:45:29Z
 not_after   2046-11-15 04:45:29Z
 issuer      ac8d20719c099758def8e7d932b19cde
Update key created: UPDATE-PRIMARY
 type        certificate
 bytes       173
 serial      ee169828f4e380b216784e5a878ad7ed
 role        update
 model       UPDATE-PRIMARY
 sign_pk     f3628c241433f53ca072db499fccb31f79ac63ea2553223292eb9d8771db5d74
 not_before  2026-11-20 04:45:29Z
 not_after   2036-11-17 04:45:29Z
 issuer      ac8d20719c099758def8e7d932b19cde
Update key created: UPDATE-BACKUP
 type        certificate
 bytes       172
 serial      e47a66f6bc04fe25c191bf644d8e9bde
 role        update
 model       UPDATE-BACKUP
 sign_pk     d018d890fcc95031301bd3f8aa55e4d67e91ac07deb8be23f40641901209b315
 not_before  2026-11-20 04:45:29Z
 not_after   2036-11-17 04:45:29Z
 issuer      ac8d20719c099758def8e7d932b19cde
> Provisioning devices...
sudo: /etc/sudoers.d is not a regular file

== Issuer -> station: public certificates
/srv/public/root.cert
/srv/public/update-primary.cert
/srv/public/update-backup.cert
trust anchor ac8d20719c099758def8e7d932b19cde installed
sudo: /etc/sudoers.d is not a regular file

== Device acme-server generates its own keys (0.3)
serial 594f379f9710e1374d95fda6043d7ba7
serial=594f379f9710e1374d95fda6043d7ba7

== Station -> issuer: signing requests (0.4)
1 request(s) exported
SIGNED   594f379f9710e1374d95fda6043d7ba7.csr: server SERVER-1 594f379f9710e1374d95fda6043d7ba7
1 signed, 0 rejected

== Issuer -> station: certificates
VERIFIED 594f379f9710e1374d95fda6043d7ba7

== Station -> device acme-server: image assembly (0.5)
exported certificates to /srv/out
installed serial=594f379f9710e1374d95fda6043d7ba7 role=server

== Registration on the server (0.6)
new    594f379f9710e1374d95fda6043d7ba7.cert
new    update-backup.cert
new    update-primary.cert
sudo: /etc/sudoers.d is not a regular file

== Device acme-console generates its own keys (0.3)
serial 15b4a0561d42abb01e17227f6b0a7f83
serial=15b4a0561d42abb01e17227f6b0a7f83

== Station -> issuer: signing requests (0.4)
1 request(s) exported
SIGNED   15b4a0561d42abb01e17227f6b0a7f83.csr: console CONSOLE-X1 15b4a0561d42abb01e17227f6b0a7f83
1 signed, 0 rejected

== Issuer -> station: certificates
VERIFIED 15b4a0561d42abb01e17227f6b0a7f83

== Station -> device acme-console: image assembly (0.5)
exported certificates to /srv/out
installed serial=15b4a0561d42abb01e17227f6b0a7f83 role=console

== Registration on the server (0.6)
new    15b4a0561d42abb01e17227f6b0a7f83.cert
known  update-backup.cert
known  update-primary.cert
sudo: /etc/sudoers.d is not a regular file

== Station generates the cartridge keys (0.3)
serial 308f813a2164e57ab1ec70743b4401e6

== Station -> issuer: signing requests (0.4)
1 request(s) exported
SIGNED   308f813a2164e57ab1ec70743b4401e6.csr: cartridge CART-A1 308f813a2164e57ab1ec70743b4401e6
1 signed, 0 rejected

== Issuer -> station: certificates
VERIFIED 308f813a2164e57ab1ec70743b4401e6

== Station -> device acme-cartridge: image assembly (0.5)
exported cartridge image to /srv/out
installed serial=308f813a2164e57ab1ec70743b4401e6 role=cartridge

== Station erases its copy of the cartridge keys
station copy of 308f813a2164e57ab1ec70743b4401e6 erased: device.secret, sign.key.enc, enc.key.enc, role, request.csr, root.cert, device.cert, update-primary.cert, update-backup.cert

== Registration on the server (0.6)
new    308f813a2164e57ab1ec70743b4401e6.cert
known  update-backup.cert
known  update-primary.cert
> Running Phase 0 validations...

======================================================================
Section 1: Design Attributes

----------------------
>> One Trust Anchor (Offline)
----------------------
> Should print 'lo':
lo
> Print the network status of each container:
acme-issuer: none
acme-provision: none
acme-server: acme-net
acme-console: acme-net
acme-cartridge: none
> One root cert eberywhere, all hashes should look identical:
a19f7ebc6772a63837dc0e35363ba37db65b817dcfd66423a5b8095a5e0209c4  /var/lib/acme-issuer/root/root.cert
a19f7ebc6772a63837dc0e35363ba37db65b817dcfd66423a5b8095a5e0209c4  /var/lib/acme-station/trust/root.cert
a19f7ebc6772a63837dc0e35363ba37db65b817dcfd66423a5b8095a5e0209c4  /var/lib/acme-device/root.cert
a19f7ebc6772a63837dc0e35363ba37db65b817dcfd66423a5b8095a5e0209c4  /var/lib/acme-device/root.cert
a19f7ebc6772a63837dc0e35363ba37db65b817dcfd66423a5b8095a5e0209c4  /var/lib/acme-device/root.cert
> The root PK exists only in the issuer:
acme-provision: 0 root.key files
acme-server: 0 root.key files
acme-console: 0 root.key files
acme-cartridge: 0 root.key files
> Self-signed, role is root and the issuer serial equals its own serial:
/var/lib/acme-issuer/root/root.cert
 type        certificate
 bytes       168
 serial      ac8d20719c099758def8e7d932b19cde
 role        root
 model       ACME-ROOT
 sign_pk     d0d49b65a2da2d687342e9881aee5546e805a132df0ecfdfb2d47688c8e2ac42
 not_before  2026-11-20 04:45:29Z
 not_after   2046-11-15 04:45:29Z
 issuer      ac8d20719c099758def8e7d932b19cde

----------------------
>> Per-Device Identities
----------------------
> Print out identites. All have a different serial and PK (Note: Phase 0 does not revocation yet so the status column in the reg are for later:
== acme-server
 serial      594f379f9710e1374d95fda6043d7ba7
 role        server
 sign_pk     e17214b96b6add3b7eb2b30f6287f1f0503734f9d7977be61c6258833911d019
== acme-console
 serial      15b4a0561d42abb01e17227f6b0a7f83
 role        console
 sign_pk     fbb3a48ff217b4e7e8487f16a80bf831a2a74b4ca7a0042efc5c6a2d15384ebc
== acme-cartridge
 serial      308f813a2164e57ab1ec70743b4401e6
 role        cartridge
 sign_pk     7634e03deb62e1a9259b7f82ad674e1623da95f2033d0bbbb7939fe132de75f3
accepted: 594f379f9710e1374d95fda6043d7ba7
revoked -> revoked

----------------------
>> Roles
----------------------
CARTRIDGE accepted
CONSOLE rejected: wrong_role: Expect CONSOLE, got CARTRIDGE
SERVER rejected: wrong_role: Expect SERVER, got CARTRIDGE
refused: wrong_role: Role cannot be requested

----------------------
>> Key Separation
----------------------
> Console, two SK; Server and Cartridge, one SK:
== acme-console
enc.key.enc
sign.key.enc
update-backup.cert
update-primary.cert
== acme-server
sign.key.enc
== acme-cartridge
sign.key.enc
 sign_pk     fbb3a48ff217b4e7e8487f16a80bf831a2a74b4ca7a0042efc5c6a2d15384ebc
 enc_pk      31e26d0da3f36b5609aefcdb7d439d32d24814136b2d0d20d55dfcb66c764260
  private keys  unlocked, match certificate (sign+enc)
  update certs  2
> Update keys live apart from the issueing key, with diff PK:
/var/lib/acme-issuer/root:
total 8
-rw------- 1 root root 168 Nov 20 04:45 root.cert
-rw------- 1 root root  32 Nov 20 04:45 root.key

/var/lib/acme-issuer/update:
total 16
-rw------- 1 root root 172 Nov 20 04:45 backup.cert
-rw------- 1 root root  32 Nov 20 04:45 backup.key
-rw------- 1 root root 173 Nov 20 04:45 primary.cert
-rw------- 1 root root  32 Nov 20 04:45 primary.key
 model       ACME-ROOT
 sign_pk     d0d49b65a2da2d687342e9881aee5546e805a132df0ecfdfb2d47688c8e2ac42
 model       UPDATE-PRIMARY
 sign_pk     f3628c241433f53ca072db499fccb31f79ac63ea2553223292eb9d8771db5d74

----------------------
>> Software Key Storage (AES-256-GCM)
----------------------
> Software Storage keys (file is 60-bytes: 12-byte nonce, 32-byte key encrypt, and 16-byte GCM tag):
total 20
-rw-r--r-- 1 root root 166 Nov 20 04:45 device.cert
-rw------- 1 root root  32 Nov 20 04:45 device.secret
-rw-r--r-- 1 root root  10 Nov 20 04:45 role
-rw-r--r-- 1 root root 168 Nov 20 04:45 root.cert
-rw------- 1 root root  60 Nov 20 04:45 sign.key.enc
60 /var/lib/acme-device/sign.key.enc
 82 a0 fc 7a 46 5f 1b b6 1e 7e 3d 04 a0 de 0a cc
 45 39 44 04 d1 d2 96 9e f1 f4 05 f1 5f a2 1a cc
 c1 8d e1 d1 cd c2 73 ef ec f0 8f 12 cb aa 9a 04
 e3 c9 29 7b 26 0e 77 23 9b 20 fe cb
  private keys  unlocked, match certificate (sign)
> Tamper test (copy of /tmp/img):
state: provisioned
error: cannot unlock private key: AEAD Authentication Failed
> KEK Recompute Check (Obfuscation, not protection), recomputing the KEK from files already on the device and prints whether it matches:
recovered key matches certificate: True

----------------------
>> Compact Certificate Format
----------------------
/var/lib/acme-issuer/root/root.cert
 type        certificate
 bytes       168
 serial      ac8d20719c099758def8e7d932b19cde
 role        root
 model       ACME-ROOT
 sign_pk     d0d49b65a2da2d687342e9881aee5546e805a132df0ecfdfb2d47688c8e2ac42
 not_before  2026-11-20 04:45:29Z
 not_after   2046-11-15 04:45:29Z
 issuer      ac8d20719c099758def8e7d932b19cde
total bytes: 166  signature bytes: 64
1 1
2 308f813a2164e57ab1ec70743b4401e6
3 3
4 CART-A1
5 7634e03deb62e1a9259b7f82ad674e1623da95f2033d0bbbb7939fe132de75f3
7 1795149936
8 2110509936
9 ac8d20719c099758def8e7d932b19cde
> keys 1 to 9 are version, serial, role, model, signing key, validity (7 and 8), and issuer; key 6 is the console-only encryption key. The whole certificate is well under the 512-byte limit. The parser is strict:
trailing byte -> malformed: non-deterministic CBOR or trailing data
truncated -> malformed: Not valid CBOR

----------------------
>> Modern Small Algorithms (Ed25519 and X25519)
----------------------
sign_pk 32 sig 64 dh_pk 32 bytes
X25519 both sides agree: True
Ed25519 good/tampered: True False
libsodium binding 1.5.0 / cryptography 43.0.0

----------------------
>> Device Registry
----------------------
> Only accepts certs that are ACME signed (Five rows: server, console, cartridge, two update keys; all active and the junk cert is REJECTED):
594f379f9710e1374d95fda6043d7ba7  server    SERVER-1         active   2026-11-20 04:45:32Z
e47a66f6bc04fe25c191bf644d8e9bde  update    UPDATE-BACKUP    active   2026-11-20 04:45:32Z
ee169828f4e380b216784e5a878ad7ed  update    UPDATE-PRIMARY   active   2026-11-20 04:45:32Z
15b4a0561d42abb01e17227f6b0a7f83  console   CONSOLE-X1       active   2026-11-20 04:45:35Z
308f813a2164e57ab1ec70743b4401e6  cartridge CART-A1          active   2026-11-20 04:45:37Z
serial                            role       model           status
--------------------------------  ---------  --------------  ------
594f379f9710e1374d95fda6043d7ba7  server     SERVER-1        active
e47a66f6bc04fe25c191bf644d8e9bde  update     UPDATE-BACKUP   active
ee169828f4e380b216784e5a878ad7ed  update     UPDATE-PRIMARY  active
15b4a0561d42abb01e17227f6b0a7f83  console    CONSOLE-X1      active
308f813a2164e57ab1ec70743b4401e6  cartridge  CART-A1         active
CREATE TABLE devices (
    serial        TEXT PRIMARY KEY CHECK (length(serial) = 32),
    role          TEXT NOT NULL CHECK (role IN
                      ('server','console','cartridge','update')),
    model         TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN
                      ('active','revoked')),
    cert_sha256   TEXT NOT NULL,
    not_before    INTEGER NOT NULL,
    not_after     INTEGER NOT NULL,
    registered_at INTEGER NOT NULL,
    updated_at    INTEGER NOT NULL
);
REJECTED x.cert: malformed: Not valid CBOR
exit=1

======================================================================
Section 2: Protocols

----------------------
>> Root Generation and Update Keys (Offline)
----------------------
> One root line, two update lines:
ac8d20719c099758def8e7d932b19cde  root      ACME-ROOT
ee169828f4e380b216784e5a878ad7ed  update    UPDATE-PRIMARY
e47a66f6bc04fe25c191bf644d8e9bde  update    UPDATE-BACKUP
594f379f9710e1374d95fda6043d7ba7  server    SERVER-1
15b4a0561d42abb01e17227f6b0a7f83  console   CONSOLE-X1
308f813a2164e57ab1ec70743b4401e6  cartridge CART-A1
/var/lib/acme-issuer/root:
total 8
-rw------- 1 root root 168 Nov 20 04:45 root.cert
-rw------- 1 root root  32 Nov 20 04:45 root.key

/var/lib/acme-issuer/update:
total 16
-rw------- 1 root root 172 Nov 20 04:45 backup.cert
-rw------- 1 root root  32 Nov 20 04:45 backup.key
-rw------- 1 root root 173 Nov 20 04:45 primary.cert
-rw------- 1 root root  32 Nov 20 04:45 primary.key
> Refuse to overwrite:
error: Root already exists, will not overwrite
exit=2
> Same:
error: Update kesy already exist; not overwriting.
exit=2
> Air-gap guard check via throwawy container (Refuses before generating anything):
error: Network interfece(s) currently present: eth0 > The issuer needs to be air-gapped; remove the interface or bypass by adding: --allow-network
exit=2

----------------------
>> Device Key Generation (Scratch Image)
----------------------
> Use a scratch image so the real console is untouched. The device generates its own keys, and status says 'state:pending'. The request holds public data and the proof of possession; show labels it 'type: request':
serial=38a0427ce3efcf0e4964adb7452cc0e8
total 20
-rw------- 1 root root  32 Nov 20 04:45 device.secret
-rw------- 1 root root  60 Nov 20 04:45 enc.key.enc
-rw-r--r-- 1 root root 176 Nov 20 04:45 request.csr
-rw-r--r-- 1 root root   8 Nov 20 04:45 role
-rw------- 1 root root  60 Nov 20 04:45 sign.key.enc
state: pending
/tmp/demo-out/request.csr
 type        request
 bytes       176
 serial      38a0427ce3efcf0e4964adb7452cc0e8
 role        console
 model       DEMO-CONSOLE
 sign_pk     34cf911a2263591e0c919cdd01feb29062e08de4450df56f5bf6f21468bcf7d8
 enc_pk      62fe7f7533d95c4f094e8eb18f6884327c458ea4070e168ffb0b01d7ac898906

----------------------
>> Cert Issuance & Duplicate Rejection
----------------------
> Leave a DEMO-CONSOLE entry in the issuer's append-only log, which is harmless and identifiable:
SIGNED   demo.csr: console DEMO-CONSOLE 38a0427ce3efcf0e4964adb7452cc0e8
1 signed, 0 rejected
/srv/demo-out/38a0427ce3efcf0e4964adb7452cc0e8.cert
 type        certificate
 bytes       206
 serial      38a0427ce3efcf0e4964adb7452cc0e8
 role        console
 model       DEMO-CONSOLE
 sign_pk     34cf911a2263591e0c919cdd01feb29062e08de4450df56f5bf6f21468bcf7d8
 enc_pk      62fe7f7533d95c4f094e8eb18f6884327c458ea4070e168ffb0b01d7ac898906
 not_before  2026-11-20 04:45:42Z
 not_after   2036-11-17 04:45:42Z
 issuer      ac8d20719c099758def8e7d932b19cde
0 signed, 1 rejected
REJECTED demo.csr: serial 38a0427ce3efcf0e4964adb7452cc0e8 was already issued
exit=1
> Cleaning up demo CSR/Cert files:

----------------------
>> Image Assembly and Registration (Re-provisioning Cartridge)
----------------------
> Runs the whole flow with a heading per step, erase the cartridge and provision it again:
erased: device.secret, sign.key.enc, enc.key.enc, role, request.csr, root.cert, device.cert, update-primary.cert, update-backup.cert

== Station generates the cartridge keys (0.3)
serial 8be991478985b27bd95d35f801f18a2b

== Station -> issuer: signing requests (0.4)
1 request(s) exported
shred: /srv/xfer.tar: failed to open for writing: Permission denied
> Station generates keys, issuer signs, station verifies, image assembly, station erasing its copy, and registration:
> Image contents:
total 0
> Comapre, console has more:
total 32
-rw-r--r-- 1 root root 204 Nov 20 04:45 device.cert
-rw------- 1 root root  32 Nov 20 04:45 device.secret
-rw------- 1 root root  60 Nov 20 04:45 enc.key.enc
-rw-r--r-- 1 root root   8 Nov 20 04:45 role
-rw-r--r-- 1 root root 168 Nov 20 04:45 root.cert
-rw------- 1 root root  60 Nov 20 04:45 sign.key.enc
-rw-r--r-- 1 root root 172 Nov 20 04:45 update-backup.cert
-rw-r--r-- 1 root root 173 Nov 20 04:45 update-primary.cert
> No 'keys held':
pending  8be991478985b27bd95d35f801f18a2b (keys held)
issued   15b4a0561d42abb01e17227f6b0a7f83
issued   308f813a2164e57ab1ec70743b4401e6
issued   594f379f9710e1374d95fda6043d7ba7
> Empty:
8be991478985b27bd95d35f801f18a2b
> New cartridge row:
594f379f9710e1374d95fda6043d7ba7  server    SERVER-1         active   2026-11-20 04:45:32Z
e47a66f6bc04fe25c191bf644d8e9bde  update    UPDATE-BACKUP    active   2026-11-20 04:45:32Z
ee169828f4e380b216784e5a878ad7ed  update    UPDATE-PRIMARY   active   2026-11-20 04:45:32Z
15b4a0561d42abb01e17227f6b0a7f83  console   CONSOLE-X1       active   2026-11-20 04:45:35Z
308f813a2164e57ab1ec70743b4401e6  cartridge CART-A1          active   2026-11-20 04:45:37Z
> Prints 'known':
known  308f813a2164e57ab1ec70743b4401e6.cert
known  update-backup.cert
known  update-primary.cert

======================================================================
Section 3: Implementations

----------------------
>> Implementation & Code Checks
----------------------
> Pinned Crypto Library; lists only 'crypto.py'. Every other file calls its functions:
/opt/acme/acme/crypto.py
> Defined Cert Format, Shows the format header:
# Name: cert.py
# Nodes: ALL (/opt/acme/acme/)
# Purpose: Creates a compact certificate format for all nodes
# Notes:
#   - X NOT BEFORE and X NOT AFTER is describing the validity periodd during cert is active
#   - Following the wire format for CBOR
#   - cert = [ tbs : bstr, sig : bstr(64) ]
#   - sig  = Ed25519(issuer_sk, "ACME-CERT-v1" || tbs)
#   - tbs  = CBOR map, integer keys, with 9 identity fields.
#   - The signatire will cover the same bytes tbs as recived to prevent the need for verification re-encoding.
#   - verify_cert() will be the only way to turn bytes into a cert for a peer (checking signer, role, validatity, and possible revocation status)
# ===================================================================
# Libraries:

import time
import cbor2
from . import crypto
from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, Optional
> Offline Issuer Tool, the console's 'update certs 2' from status:
usage: acme-issuer [-h] [--home HOME] [--allow-network]
                   {init-root,init-update-keys,sign,export-public,show,list} ...

Offline ACME certificate issuer

positional arguments:
  {init-root,init-update-keys,sign,export-public,show,list}
    init-root           0.1 generate and self-sign Cert_ACME
    init-update-keys    0.2 generate primary and backup update keys
    sign                0.4 sign every *.csr in INBOX
    export-public       copy root and update certificates to DEST
    show                decode a certificate or request
    list                list every certificate issued

options:
  -h, --help            show this help message and exit
  --home HOME
  --allow-network       development only: run with a network interface
  private keys  unlocked, match certificate (sign+enc)
  update certs  2
> Provisioning usage and status:
Usage: ./provision.sh COMMAND [MODEL]

  trust                 give the station Cert_ACME + update certs
  server    MODEL       provision the server      (do this first)
  console   MODEL       provision the console
  cartridge MODEL       provision the cartridge
  status                show every device and the registry

Override container names with ISSUER=, STATION=, SERVER=, CONSOLE=, CARTRIDGE=.
Ignore network air-gap by adding: ISSUER_FLAGS=--allow-network

== Device acme-server
state: provisioned
 type        certificate
 bytes       167
 serial      594f379f9710e1374d95fda6043d7ba7
 role        server
 model       SERVER-1
 sign_pk     e17214b96b6add3b7eb2b30f6287f1f0503734f9d7977be61c6258833911d019
 not_before  2026-11-20 04:45:31Z
 not_after   2036-11-17 04:45:31Z
 issuer      ac8d20719c099758def8e7d932b19cde
  trust anchor  ac8d20719c099758def8e7d932b19cde
  private keys  unlocked, match certificate (sign)
  update certs  0

== Device acme-console
state: provisioned
 type        certificate
 bytes       204
 serial      15b4a0561d42abb01e17227f6b0a7f83
 role        console
 model       CONSOLE-X1
 sign_pk     fbb3a48ff217b4e7e8487f16a80bf831a2a74b4ca7a0042efc5c6a2d15384ebc
 enc_pk      31e26d0da3f36b5609aefcdb7d439d32d24814136b2d0d20d55dfcb66c764260
 not_before  2026-11-20 04:45:34Z
 not_after   2036-11-17 04:45:34Z
 issuer      ac8d20719c099758def8e7d932b19cde
  trust anchor  ac8d20719c099758def8e7d932b19cde
  private keys  unlocked, match certificate (sign+enc)
  update certs  2

== Device acme-cartridge
state: empty

== Station
pending  8be991478985b27bd95d35f801f18a2b (keys held)
issued   15b4a0561d42abb01e17227f6b0a7f83
issued   308f813a2164e57ab1ec70743b4401e6
issued   594f379f9710e1374d95fda6043d7ba7

== Registry
594f379f9710e1374d95fda6043d7ba7  server    SERVER-1         active   2026-11-20 04:45:32Z
e47a66f6bc04fe25c191bf644d8e9bde  update    UPDATE-BACKUP    active   2026-11-20 04:45:32Z
ee169828f4e380b216784e5a878ad7ed  update    UPDATE-PRIMARY   active   2026-11-20 04:45:32Z
15b4a0561d42abb01e17227f6b0a7f83  console   CONSOLE-X1       active   2026-11-20 04:45:35Z
308f813a2164e57ab1ec70743b4401e6  cartridge CART-A1          active   2026-11-20 04:45:37Z

----------------------
>> Unit-Tested Trust Checks
----------------------
........................................................................ [ 72%]
............................                                             [100%]
100 passed in 0.74s
============================= test session starts ==============================
platform linux -- Python 3.13.5, pytest-8.3.5, pluggy-1.5.0 -- /usr/bin/python3
rootdir: /opt/acme
collecting ... collected 56 items / 18 deselected / 38 selected

tests/test_cert.py::test_wrong_signer PASSED                             [  2%]
tests/test_cert.py::test_wrong_role[3-2] PASSED                          [  5%]
tests/test_cert.py::test_wrong_role[3-1] PASSED                          [  7%]
tests/test_cert.py::test_wrong_role[2-1] PASSED                          [ 10%]
tests/test_cert.py::test_wrong_role[1-4] PASSED                          [ 13%]
tests/test_cert.py::test_wrong_role[4-2] PASSED                          [ 15%]
tests/test_cert.py::test_expired PASSED                                  [ 18%]
tests/test_cert.py::test_not_yet_valid PASSED                            [ 21%]
tests/test_cert.py::test_revoked PASSED                                  [ 23%]
tests/test_cert.py::test_garbage[] PASSED                                [ 26%]
tests/test_cert.py::test_garbage[\x00] PASSED                            [ 28%]
tests/test_cert.py::test_garbage[not cbor at all] PASSED                 [ 31%]
tests/test_cert.py::test_garbage[\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff] PASSED [ 34%]
tests/test_cert.py::test_garbage[\x82@] PASSED                           [ 36%]
tests/test_cert.py::test_garbage[AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA] PASSED [ 39%]
tests/test_cert.py::test_correctly_signed_but_malformed[unknown_field] PASSED [ 42%]
tests/test_cert.py::test_correctly_signed_but_malformed[text_key] PASSED [ 44%]
tests/test_cert.py::test_correctly_signed_but_malformed[missing_serial] PASSED [ 47%]
tests/test_cert.py::test_correctly_signed_but_malformed[missing_role] PASSED [ 50%]
tests/test_cert.py::test_correctly_signed_but_malformed[missing_validity] PASSED [ 52%]
tests/test_cert.py::test_correctly_signed_but_malformed[bad_version] PASSED [ 55%]
tests/test_cert.py::test_correctly_signed_but_malformed[short_serial] PASSED [ 57%]
tests/test_cert.py::test_correctly_signed_but_malformed[serial_as_text] PASSED [ 60%]
tests/test_cert.py::test_correctly_signed_but_malformed[unknown_role] PASSED [ 63%]
tests/test_cert.py::test_correctly_signed_but_malformed[role_as_bool] PASSED [ 65%]
tests/test_cert.py::test_correctly_signed_but_malformed[role_as_text] PASSED [ 68%]
tests/test_cert.py::test_correctly_signed_but_malformed[empty_model] PASSED [ 71%]
tests/test_cert.py::test_correctly_signed_but_malformed[long_model] PASSED [ 73%]
tests/test_cert.py::test_correctly_signed_but_malformed[short_sign_pk] PASSED [ 76%]
tests/test_cert.py::test_correctly_signed_but_malformed[negative_time] PASSED [ 78%]
tests/test_cert.py::test_correctly_signed_but_malformed[inverted_window] PASSED [ 81%]
tests/test_cert.py::test_correctly_signed_but_malformed[cartridge_with_enc_pk] PASSED [ 84%]
tests/test_cert.py::test_correctly_signed_but_malformed[console_without_enc_pk] PASSED [ 86%]
tests/test_cert.py::test_correctly_signed_but_malformed[console_short_enc_pk] PASSED [ 89%]
tests/test_cert.py::test_correctly_signed_but_malformed[tbs_not_a_map] PASSED [ 92%]
tests/test_cert.py::test_correctly_signed_but_malformed[tbs_not_cbor] PASSED [ 94%]
tests/test_cert.py::test_correctly_signed_but_malformed[tbs_trailing_bytes] PASSED [ 97%]
tests/test_cert.py::test_correctly_signed_but_malformed[non_deterministic] PASSED [100%]

====================== 38 passed, 18 deselected in 0.06s =======================
Finished!
