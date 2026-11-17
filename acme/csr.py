# Name: csr.py
# Nodes: ALL (/opt/acme/acme/)
# Purpose: Aides in the signing request, checking what device/provisioning station will be handed off to the issuer
# Notes:
#   - Envelope error = the crypographic wrapper failed (e.g., payload data and signature are incorrect)
#   - canonical = True enforces that it is deterministic, unqiue and standardized encoding
#   - csr  = [ body : bstr, sig : bstr(64) ]
#   - sig  = Ed25519(device_sign_sk, "ACME-CSR-v1" || body)   proof of possession
#   - body = CBOR map: 1 ver, 2 serial, 3 role, 4 model, 5 sign_pk, [6 enc_pk]
# ===================================================================
# libraries

from dataclasses import dataclass
from typing import Optional
import cbor2
from . import cert as C
from . import crypto
from .cert import CertError, Role

# ===================================================================
# CSR template

SIG_CONTEXT = b"ACME-CSR-v1"
MAX_CSR_LEN = 512
REQUESTABLE = (Role.SERVER, Role.CONSOLE, Role.CARTRIDGE)

# Template for request 
@dataclass(frozen=True)
class Request:
    serial: bytes
    role: Role
    model: str
    sign_pk: bytes
    enc_pk: Optional[bytes]

# ===================================================================
# Fucntions

def _check(body) -> None:
    if type(body) is not dict:
        raise CertError("malformed", "Request body is not a map")
    probe = dict(body)
    if {C.K_NOT_BEFORE, C.K_NOT_AFTER, C.K_ISSUER} & set(probe):
        raise CertError("malformed", "unkown field")
    probe.update({C.K_NOT_BEFORE: 0, C.K_NOT_AFTER: 0, C.K_ISSUER: bytes(C.SERIAL_LEN)})
    C._check_fields(probe)
    if body[C.K_ROLE] not in REQUESTABLE:
        raise CertError("wrong_role", "Role cannot be requested")
    # end

def make_csr(sign_sk: bytes, *, serial: bytes, role: Role, model: str, enc_pk: Optional[bytes] = None) -> bytes:
    body = {C.K_VER: C.CERT_VERSION, C.K_SERIAL: serial, C.K_ROLE: int(role), C.K_MODEL: model, C.K_SIGN_PK: crypto.sign_public(sign_sk)}
    if enc_pk is not None:
        body[C.K_ENC_PK] = enc_pk
    _check(body)
    raw = cbor2.dumps(body, canonical=True)
    return cbor2.dumps([raw, crypto.sign(sign_sk, SIG_CONTEXT + raw)], canonical=True)
    # end

def parse_csr(raw: bytes) -> Request:
    # Parse a request and verify its proof-of-possesion signature
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_CSR_LEN:
        raise CertError("malformed", "Bad length")
    # Envelope, not environment
    env = C._loads_strict(raw)
    if (type(env) is not list or len(env) != 2 or type (env[0]) is not bytes or type(env[1]) is not bytes or len(env[1]) != crypto.SIG_LEN):
        raise CertError("malformed", "envelope")
    body = C._loads_strict(env[0])
    _check(body)
    if not crypto.verify(body[C.K_SIGN_PK], SIG_CONTEXT + env[0], env[1]):
        raise CertError("bad_signature", "Proof of Possesion Failed")
    return Request(serial=body[C.K_SERIAL], role=Role(body[C.K_ROLE]), model=body[C.K_MODEL], sign_pk=body[C.K_SIGN_PK], enc_pk=body.get(C.K_ENC_PK))
    # end