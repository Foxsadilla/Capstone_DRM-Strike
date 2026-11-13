# Name: crypto.py
# Nodes: ALL (/opt/acme/acme/)
# Purpose: Creates all the crypto functons that the other modules will call to imporve negotiations between.
# Notes:
#   -   Signatures : Ed25519            (libsodium via PyNaCl)
#   -   Key agree. : X25519             (libsodium via PyNaCl)
#   -   KDF        : HKDF-SHA256        (cryptography)
#   -   AEAD       : AES-256-GCM        (cryptography)
#   -   HMAC-based Extract-and-Expand Key Derivation Function (HKDF)
# ===================================================================
# Libraries:

import os

from nacl import bindings as _sodium
from nacl import exceptions as _nacl_exc
from nacl import public as _nacl_public
from nacl import signing as _nacl_signing
from cryptography.hazmat.primitives import hashes as _hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF as _HKDF

# ===================================================================
# Ed25519 seed

SIGN_SK_LEN = 32   
SIGN_PK_LEN = 32
SIG_LEN = 64
DH_SK_LEN = 32
DH_PK_LEN = 32
AEAD_KEY_LEN = 32
AEAD_NONCE_LEN = 12

ECDH_Key = "X25519" # Elliptic Curve Diffie-Hellman key agreement algorithm being used. I can't spell this repeatdily
# ===================================================================

class CryptoError(Exception):
    """ Failure or bad key during decryption/authentication! """
    # end

def random(n: int) -> bytes:
    return os.urandom(n)
    # end

# ===================================================================
# Signatures
def sign_keygen() -> tuple[bytes, bytes]:
    sk = _nacl_signing.SigningKey.generate()
    return sk.encode(), sk.verify_key.encode()
    # end

def sign_public(sk: bytes) -> bytes:
    return _nacl_signing.SigningKey(sk).verify_key.encode()
    # end

def sign(sk: bytes, msg: bytes) -> bytes:
    return _nacl_signing.SigningKey(sk).sign(msg).signature
    # end

def verify(pk: bytes, msg: bytes, sig: bytes) -> bool:
    if len(pk) != SIGN_PK_LEN or len(sig) != SIG_LEN:
        return False
    try:
        _nacl_signing.VerifyKey(pk).verify(msg, sig)
        return True
    except (_nacl_exc.BadSignatureError, ValueError, TypeError):
        return False    
    # end

# ===================================================================
# Key Agreement

def dh_keygen() -> tuple[bytes, bytes]:
    sk = _nacl_public.PrivateKey.generate()
    return sk.encode(), sk.public_key.encode()
    # end; i.e., return secret key and public key

def dh_public(sk: bytes) -> bytes:
    return _nacl_public.PrivateKey(sk).public_key.encode()
    # end

def dh(sk: bytes, peer_pk: bytes) -> bytes:
    # Create the Rar X35519 shared secret that should always be passed through hkdf()
    if len(sk) != DH_SK_LEN or len(peer_pk) != DH_PK_LEN:
        raise CryptoError(f"BAD {ECDH_Key} key length")
    try:
        shared = _sodium.crypto_scalarmult(sk, peer_pk)
    except Exception as e:
        raise CryptoError(f"{ECDH_Key} FAILED") from e
    if shared == bytes(32):
        raise CryptoError(f"{ECDH_Key} produced an all-zero secret!")
    return shared
    # end

# ===================================================================
# KDF

def hkdf(ikm: bytes, salt: bytes, info: bytes, length: int = 32) -> bytes:
    # ikm = Input Key Material, salt = rndm num string, info = pub string for binding derived key, & length = size
    return _HKDF(algorithm=_hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)
    # end

# ===================================================================
# AEAD - Authenticated Encryption with Associated Data

def aead_encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    # Return the nonce, ciphertext, nd tag with a new rndm nonce 
    if len(key) != AEAD_KEY_LEN:
        raise CryptoError("BAD AEAD key length")
    nonce = random(AEAD_NONCE_LEN)
    return nonce + _AESGCM(key).encrypt(nonce, plaintext, aad)
    # end

def aead_decrypt(key: bytes, blob: bytes, aad: bytes = b"") -> bytes:
    if len(key) != AEAD_KEY_LEN or len(blob) < AEAD_NONCE_LEN + 16:
        raise CryptoError("BAD AEAD Input.")
    try:
        return _AESGCM(key).decrypt(blob[:AEAD_NONCE_LEN], blob[AEAD_NONCE_LEN:], aad)
    except Exception as e:
        raise CryptoError("AEAD Authentication Failed") from e
    # end
