# Name: keystore.py
# Nodes: ALL (/opt/acme/acme/)
# Purpose: Device image and software key storage
# Notes:
#   - Purpose is obfuscation
#   - KEK - Key Encryption Key
# ===================================================================
# Libraries & global vals

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import cert as C
from . import crypto
from . import csr as R
from .cert import CertError, Role

# Pseudo constant for simulated firmware:
FIRMWARE_CONSTANT = bytes.fromhex("41434d452d4649524d574152452d76312d6b657973746f72652d73616c742121")

DEVICE_ROLES = (Role.SERVER, Role.CONSOLE, Role.CARTRIDGE)
UPDATE_CERTS = ("update-primary.cert", "update-backup.cert")
SECRET_FILES = ("device.secret", "sign.key.enc", "enc.key.enc")
ALL_FILES = SECRET_FILES + ("role", "request.csr", "root.cert", "device.cert") + UPDATE_CERTS

class KeystoreError(Exception):
    pass

# Identity template:
@dataclass(frozen=True)
class Identity:
    # Verified device identity with its private keys set to unlocked:
    cert: C.Certificate
    anchor: C.Certificate
    sign_sk: bytes
    enc_sk: Optional[bytes]
    update_certs: tuple

# ===================================================================
# Functuons

# key encryption key
def _kek(secret: bytes, role: Role, serial: bytes) -> bytes:
    return crypto.hkdf(secret, FIRMWARE_CONSTANT, b"ACME-KEK-v1" + bytes([int(role)]) + serial)

# additional authentication data
def _aad(serial: bytes, name: str) -> bytes:
    return b"ACME-LEY-v1|" + serial + b"|" + name.encode()

def _write(path: Path, data: bytes, mode: int = 0o644) -> None:
    # File descriptor:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(path, mode)

def wipe(path: Path) -> None:
    # Overwrites then deletes
    if path.exists():
        n = path.stat().st_size
        with open(path, "r+b") as f:
            f.write(os.urandom(n))
            f.flush()
            os.fsync(f.fileno())
        path.unlink()

# Device image template:
class DeviceImage:
    def __init__(self, home):
        self.home = Path(home)

    def _p(self, name: str) -> Path:
        return self.home / name

    def state(self) -> str:
        if self._p("device.cert").exists():
            return "provisioned"
        if self._p("request.csr").exists():
            return "pending"
        return "empty"

    def role(self) -> Role:
        try:
            return Role[self._p("role").read_text().strip().upper()]
        except (OSError, KeyError) as e:
            raise KeystoreError("Image has no valid role file") from e

    # Key generation:
    def create(self, role: Role, model: str, serial: Optional[bytes] = None) -> bytes:
        # Will generate the device's secret and key pairs returning the CSR
        if role not in DEVICE_ROLES:
            raise KeystoreError("not a device role")
        if self.state() != "empty":
            raise KeystoreError(f"image already exists ({self.state()})")
        serial = crypto.random(C.SERIAL_LEN) if serial is None else serial
        sign_sk, _ = crypto.sign_keygen()
        enc_sk = enc_pk = None
        if role is Role.CONSOLE:
            enc_sk, enc_pk = crypto.dh_keygen()
        # validates before any write
        csr = R.make_csr(sign_sk, serial=serial, role=role, model=model, enc_pk=enc_pk)
        self.home.mkdir(mode=0o700, parents=True, exist_ok=True)
        secret = crypto.random(32)
        kek = _kek(secret, role, serial)
        _write(self._p("role"), role.name.lower().encode() + b"\n")
        _write(self._p("device.secret"), secret, 0o600)
        _write(self._p("sign.key.enc"), crypto.aead_encrypt(
            kek, sign_sk, _aad(serial, "sign")), 0o600)
        if enc_sk is not None:
            _write(self._p("enc.key.enc"), crypto.aead_encrypt(
                kek, enc_sk, _aad(serial, "enc")), 0o600)
        _write(self._p("request.csr"), csr)
        return csr
        # emd

    # Request handling
    def request(self) -> bytes:
        if self.state() != "pending":
            raise KeystoreError("No currently pending request")
        return self._p("request.csr").read_bytes()

    # Assemble the image
    def install(self, cert_raw: bytes, root_raw: bytes, update_raws=(), now=None) -> Identity:
        # Adds certifcates to a pending image and verfies the result
        if self.state() != "pending":
            raise KeystoreError(f"image is {self.state()}, expected pending")
        role = self.role()
        req = R.parse_csr(self.request())
        anchor = C.load_trust_anchor(root_raw, now=now)
        cert = C.verify_cert(cert_raw, anchor, role, now=now)
        if (cert.serial, cert.role, cert.model, cert.sign_pk, cert.enc_pk) != (req.serial, req.role, req.model, req.sign_pk, req.enc_pk):
            raise KeystoreError("certificate does not match this device's request")
        update_raws = tuple(update_raws)
        if role is Role.CONSOLE:
            if len(update_raws) != 2:
                raise KeystoreError("a console needs both update certificates")
            # ups - update certificates
            ups = [C.verify_cert(u, anchor, Role.UPDATE, now=now)
                   for u in update_raws]
            if ups[0].sign_pk == ups[1].sign_pk:
                raise KeystoreError("primary and backup update keys are identical")
        elif update_raws:
            raise KeystoreError("only consoles carry update certificates")
        written = ["root.cert", "device.cert"]
        _write(self._p("root.cert"), root_raw)
        _write(self._p("device.cert"), cert_raw)
        for name, raw in zip(UPDATE_CERTS, update_raws):
            _write(self._p(name), raw)
            written.append(name)
        try:
            ident = self.load(role, now=now)
        except Exception:
            for name in written:
                self._p(name).unlink(missing_ok=True)
            raise
        self._p("request.csr").unlink()
        return ident

    def inject(self, src, expected_role: Role, now=None) -> Identity:
        # copies a complete image built 
        if self.state() != "empty":
            raise KeystoreError(f"image already exists ({self.state()})")
        src = Path(src)
        self.home.mkdir(mode=0o700, parents=True, exist_ok=True)
        copied = []
        try:
            for name in ALL_FILES:
                if name != "request.csr" and (src / name).is_file():
                    _write(self._p(name), (src / name).read_bytes(), 0o600 if name in SECRET_FILES else 0o644)
                    copied.append(name)
            return self.load(expected_role, now=now)
        except Exception:
            for name in copied:
                wipe(self._p(name))
            raise

    # Boot time loading
    def load(self, expected_role: Role, now=None) -> Identity:
        # verifies the whole image and unlocks the private keys
        try:
            if self.role() is not expected_role:
                raise KeystoreError("image role does not match this firmware")
            anchor = C.load_trust_anchor(self._p("root.cert").read_bytes(), now=now)
            cert = C.verify_cert(self._p("device.cert").read_bytes(), anchor, expected_role, now=now)
            kek = _kek(self._p("device.secret").read_bytes(), cert.role,
                       cert.serial)
            sign_sk = crypto.aead_decrypt(
                kek, self._p("sign.key.enc").read_bytes(),
                _aad(cert.serial, "sign"))
            if crypto.sign_public(sign_sk) != cert.sign_pk:
                raise KeystoreError("signing key does not match certificate")
            enc_sk, ups = None, ()
            if cert.role is Role.CONSOLE:
                enc_sk = crypto.aead_decrypt(
                    kek, self._p("enc.key.enc").read_bytes(),
                    _aad(cert.serial, "enc"))
                if crypto.dh_public(enc_sk) != cert.enc_pk:
                    raise KeystoreError("encryption key does not match certificate")
                ups = tuple(C.verify_cert(self._p(n).read_bytes(), anchor,
                                          Role.UPDATE, now=now)
                            for n in UPDATE_CERTS)
        except OSError as e:
            raise KeystoreError(f"incomplete image: {e}") from e
        except crypto.CryptoError as e:
            raise KeystoreError(f"cannot unlock private key: {e}") from e
        return Identity(cert, anchor, sign_sk, enc_sk, ups)

    def erase(self) -> list[str]:
        gone = []
        for name in ALL_FILES:
            wipe(self._p(name))
            gone.append(name)
        return gone
