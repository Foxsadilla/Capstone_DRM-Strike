# Name: test_crypto.py
# Nodes: ALL (/tests/)
# Purpose: Testing the crypto aspect of Phase 0
# Notes:
#   - Test sign and verify the round trip
#   - test the diffie hellman agreement
#   - Test tfor matching outputs when using HKDF with SHA-256 hash
#   -  Test Authenticated  Encryption with Associated Data tampering and roundtrip
# ===================================================================
# Libraries

import pytest
from acme import crypto

# ===================================================================
# Tests

import os

from nacl import bindings as _sodium
from nacl import exceptions as _nacl_exc
from nacl import public as _nacl_public
from nacl import signing as _nacl_signing
from cryptography.hazmat.primitives import hashes as _hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF as _HKDF

SIGN_SK_LEN = 32   # Ed25519 seed
SIGN_PK_LEN = 32
SIG_LEN = 64
DH_SK_LEN = 32
DH_PK_LEN = 32
AEAD_KEY_LEN = 32
AEAD_NONCE_LEN = 12


class CryptoError(Exception):
    """Decryption/authentication failure or bad key material."""


def random(n: int) -> bytes:
    return os.urandom(n)


# ===================================================================
# Signtatures

def sign_keygen() -> tuple[bytes, bytes]:
    # Return (secret seed, public key)
    sk = _nacl_signing.SigningKey.generate()
    return sk.encode(), sk.verify_key.encode()


def sign_public(sk: bytes) -> bytes:
    return _nacl_signing.SigningKey(sk).verify_key.encode()


def sign(sk: bytes, msg: bytes) -> bytes:
    return _nacl_signing.SigningKey(sk).sign(msg).signature


def verify(pk: bytes, msg: bytes, sig: bytes) -> bool:
    if len(pk) != SIGN_PK_LEN or len(sig) != SIG_LEN:
        return False
    try:
        _nacl_signing.VerifyKey(pk).verify(msg, sig)
        return True
    except (_nacl_exc.BadSignatureError, ValueError, TypeError):
        return False


# ===================================================================
# Key agreement

def dh_keygen() -> tuple[bytes, bytes]:
    # Returns SK, PK
    sk = _nacl_public.PrivateKey.generate()
    return sk.encode(), sk.public_key.encode()


def dh_public(sk: bytes) -> bytes:
    return _nacl_public.PrivateKey(sk).public_key.encode()


def dh(sk: bytes, peer_pk: bytes) -> bytes:
    # Raw X25519 shared secret, always pass the result through hkdf()
    if len(sk) != DH_SK_LEN or len(peer_pk) != DH_PK_LEN:
        raise CryptoError("bad X25519 key length")
    try:
        shared = _sodium.crypto_scalarmult(sk, peer_pk)
    except Exception as e:
        raise CryptoError("X25519 failed") from e
    if shared == bytes(32):
        raise CryptoError("X25519 produced all-zero secret")
    return shared


# ===================================================================
# KDF

def hkdf(ikm: bytes, salt: bytes, info: bytes, length: int = 32) -> bytes:
    return _HKDF(algorithm=_hashes.SHA256(), length=length,
                 salt=salt, info=info).derive(ikm)


# ===================================================================
# AEAD

def aead_encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    # Return nonce || ciphertext || tag, with a fresh random nonce
    if len(key) != AEAD_KEY_LEN:
        raise CryptoError("bad AEAD key length")
    nonce = random(AEAD_NONCE_LEN)
    return nonce + _AESGCM(key).encrypt(nonce, plaintext, aad)


def aead_decrypt(key: bytes, blob: bytes, aad: bytes = b"") -> bytes:
    if len(key) != AEAD_KEY_LEN or len(blob) < AEAD_NONCE_LEN + 16:
        raise CryptoError("bad AEAD input")
    try:
        return _AESGCM(key).decrypt(blob[:AEAD_NONCE_LEN],
                                    blob[AEAD_NONCE_LEN:], aad)
    except Exception as e:
        raise CryptoError("AEAD authentication failed") from e