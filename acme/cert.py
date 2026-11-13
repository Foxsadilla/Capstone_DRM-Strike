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

# ===================================================================
# Certificate Template

SIG_CONTEXT = b"ACME-CERT-v1"
CERT_VERSION = 1
SERIAL_LEN = 16
MAX_CERT_LEN = 512
MAX_MODEL_LEN = 32

K_VER, K_SERIAL, K_ROLE, K_MODEL, K_SIGN_PK, K_ENC_PK, \
    K_NOT_BEFORE, K_NOT_AFTER, K_ISSUER = range(1, 10)
_REQUIRED = {K_VER, K_SERIAL, K_ROLE, K_MODEL, K_SIGN_PK,
             K_NOT_BEFORE, K_NOT_AFTER, K_ISSUER}
_ALLOWED = _REQUIRED | {K_ENC_PK}

class Role(IntEnum):
    ROOT = 0
    SERVER = 1
    CONSOLE = 2
    CARTRIDGE = 3
    UPDATE = 4

class CertError(Exception):
    # For certificate rejection where ".reason" will be the machine-readable version
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
    # end

# Full wire encoding reusable template
@dataclass(frozen=True)
class Certificate:
    serial: bytes
    role: Role
    model: str
    sign_pk: bytes
    enc_pk: Optional[bytes]
    not_before: int
    not_after: int
    issuer: bytes
    raw: bytes # literally, the raw binary of the cert.
    # end

    @property
    def serial_hex(self) -> str:
        return self.serial.hex()
    # end

# ===================================================================
# Encoding for Issuer Side

def _encode_tbs(serial, role, model, sign_pk, enc_pk, not_before, not_after, issuer) -> bytes:
    # To Be Signed (TBS)
    tbs = {K_VER: CERT_VERSION, K_SERIAL: serial, K_ROLE: int(role),
           K_MODEL: model, K_SIGN_PK: sign_pk, K_NOT_BEFORE: not_before,
           K_NOT_AFTER: not_after, K_ISSUER: issuer}
    
    if enc_pk is not None:
        tbs[K_ENC_PK] = enc_pk
    _check_fields(tbs)
    return cbor2.dumps(tbs, canonical=True)
    # end

def issue_cert(issuer_sk: bytes, issuer_serial: bytes, *, serial: bytes, role: Role, model: str, sign_pk: bytes, enc_pk: Optional[bytes] = None, not_before: int, not_after: int) -> bytes:
    # Builds and signs the cert used by the offline issuer
    tbs = _encode_tbs(serial, role, model, sign_pk, enc_pk, not_before, not_after, issuer_serial)
    # Signature
    sig = crypto.sign(issuer_sk, SIG_CONTEXT + tbs)
    return cbor2.dumps([tbs, sig], canonical=True)
    # end

def issue_root(root_sk: bytes, *, serial: bytes, model: str = "ACME-ROOT", not_before: int, not_after: int) -> bytes:
    self_signed_trust_anchor = issue_cert(root_sk, serial, serial=serial, role=Role.ROOT, model=model, sign_pk=crypto.sign_public(root_sk), not_before=not_before, not_after=not_after)
    return self_signed_trust_anchor
    # end

# ===================================================================
# Parsing

def _is_uint(x) -> bool:
    return type(x) is int and 0 <= x < 2 ** 64
    # end

def _is_bytes(x, n) -> bool:
    return type(x) is bytes and len(x) == n
    # end

def _check_fields(tbs) -> None:
    if type(tbs) is not dict:
        raise CertError("MALFORMED", "tbs is not a map")

    keys = set(tbs.keys())

    # validator: usuing lambda as a boolean
    validation_rules = [
        (lambda: not all(type(k) is int for k in keys) or not keys <= _ALLOWED, "unknown field"),
        (lambda: not _REQUIRED <= keys, "missing field"),
        (lambda: tbs[K_VER] != CERT_VERSION or type(tbs[K_VER]) is not int, "unsupported version"),
        (lambda: not _is_bytes(tbs[K_SERIAL], SERIAL_LEN), "serial"),
        (lambda: not _is_bytes(tbs[K_ISSUER], SERIAL_LEN), "issuer"),
        (lambda: not _is_uint(tbs[K_ROLE]) or tbs[K_ROLE] not in tuple(Role), "role"),
        (lambda: type(tbs[K_MODEL]) is not str or not 1 <= len(tbs[K_MODEL]) <= MAX_MODEL_LEN, "model"),
        (lambda: not _is_bytes(tbs[K_SIGN_PK], crypto.SIGN_PK_LEN), "sign_pk"),
        (lambda: not _is_uint(tbs[K_NOT_BEFORE]) or not _is_uint(tbs[K_NOT_AFTER]), "validity"),
        (lambda: tbs[K_NOT_BEFORE] > tbs[K_NOT_AFTER], "validity window inverted"),
        (lambda: (tbs[K_ROLE] == Role.CONSOLE) != (K_ENC_PK in tbs), "enc_pk is required for consoles only"),
        (lambda: tbs[K_ROLE] == Role.CONSOLE and not _is_bytes(tbs[K_ENC_PK], crypto.DH_PK_LEN), "enc_pk"),
    ]

    for is_invalid, error_msg in validation_rules:
        if is_invalid():
            raise CertError("MALFORMED", error_msg)
    # end

def _loads_strict(data: bytes):
    # Decode the CBOR and require it to be unquie derterministic encoding (rejecting trailing bytes)
    try:
        obj = cbor2.loads(data)
        ok = cbor2.dumps(obj, canonical=True) == data
    except Exception as e:
        raise CertError("MALFORMED", "Not valid CBOR") from e
    if not ok:
        raise CertError("MALFORMED", "non-deterministic CBOR or trailing data")
    return obj
    # end

def _split(raw: bytes) -> tuple[bytes, bytes]:
    # Split the to be signed and the signature
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_CERT_LEN:
        raise CertError("MALFORMED", "Bad Length")
    env = _loads_strict(raw)
    if type(env) is not list or len(env) != 2:
        raise CertError("MALFORMED", "envelope")
    tbs, sig = env
    if type(tbs) is not bytes or not _is_bytes(sig, crypto.SIG_LEN):
        raise CertError("MALFORMED", "envelope")
    return tbs, sig
    # end

def _to_cert(tbs_bytes: bytes, raw: bytes) -> Certificate:
    tbs = _loads_strict(tbs_bytes)
    _check_fields(tbs)
    return Certificate(serial=tbs[K_SERIAL], role=Role(tbs[K_ROLE]), model=tbs[K_MODEL], sign_pk=tbs[K_SIGN_PK], enc_pk=tbs.get(K_ENC_PK), not_before=tbs[K_NOT_BEFORE], not_after=tbs[K_NOT_AFTER], issuer=tbs[K_ISSUER], raw=raw)
    # end

def _check_validity(cert: Certificate, now: Optional[int]) -> None:
    now = int(time.time()) if now is None else now
    if now < cert.not_before:
        raise CertError("Not yet valid")
    if now > cert.not_after:
        raise CertError("Expired")
    # end

def load_trust_anchor(raw: bytes, now: Optional[int] = None) -> Certificate:
    # Purpose: load the built-in ACME Cert that will earn trust from intenral image compliation.
    # The self-sig and field checks will see if there is possible corruption
    tbs_bytes, sig = _split(raw)
    cert = _to_cert(tbs_bytes, raw)
    if cert.role is not Role.ROOT or cert.issuer != cert.serial:
        raise CertError("Wrong Role", "Trust anchor must be a self-issued root")
    if not crypto.verify(cert.sign_pk, SIG_CONTEXT + tbs_bytes, sig):
        raise CertError("Bad signature")
    _check_validity(cert, now)
    return cert
    # end

def verify_cert(raw: bytes, anchor: Certificate, expected_role: Role, *, now: Optional[int] = None, is_revoked: Optional[Callable[[bytes], bool]] = None) -> Certificate:
    # Parse and verify a peer cert or output error
    # Well formed -> signed by anchor -> carries expected role -> inside valid period -> not revoked
    if not isinstance(expected_role, Role) or expected_role is Role.ROOT:
        raise ValueError("Expected role must be a non root role")
    if anchor.role is not Role.ROOT:
        raise ValueError("Anchor must be the root certificate")
    tbs_bytes, sig = _split(raw)
    if not crypto.verify(anchor.sign_pk, SIG_CONTEXT + tbs_bytes, sig):
        raise CertError("Bad signature")
    cert = _to_cert(tbs_bytes, raw)
    if cert.issuer != anchor.serial:
        raise CertError("Bad signature", "issuer serial mismatch")
    if cert.role is not expected_role:
        raise CertError("Wrong role", f"Expect {expected_role.name}, got {cert.role.name}")
    _check_validity(cert, now)
    if is_revoked is not None and is_revoked(cert.serial):
        raise CertError("revoked")
    return cert
    # end