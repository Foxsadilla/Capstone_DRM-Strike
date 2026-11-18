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


def test_sign_verify_roundtrip():
    sk, pk = crypto.sign_keygen()
    assert crypto.sign_public(sk) == pk
    sig = crypto.sign(sk, b"hello")
    assert len(sig) == crypto.SIG_LEN
    assert crypto.verify(pk, b"hello", sig)
    assert not crypto.verify(pk, b"hellp", sig)
    assert not crypto.verify(crypto.sign_keygen()[1], b"hello", sig)
    assert not crypto.verify(pk, b"hello", sig[:-1])


def test_dh_agrees():
    a_sk, a_pk = crypto.dh_keygen()
    b_sk, b_pk = crypto.dh_keygen()
    assert crypto.dh(a_sk, b_pk) == crypto.dh(b_sk, a_pk)
    with pytest.raises(crypto.CryptoError):
        crypto.dh(a_sk, b_pk[:-1])


def test_hkdf_rfc5869_case1():
    okm = crypto.hkdf(bytes.fromhex("0b" * 22),
                      bytes.fromhex("000102030405060708090a0b0c"),
                      bytes.fromhex("f0f1f2f3f4f5f6f7f8f9"), 42)
    assert okm.hex() == ("3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db0"
                         "2d56ecc4c5bf34007208d5b887185865")


def test_aead_roundtrip_and_tamper():
    key = crypto.random(32)
    blob = crypto.aead_encrypt(key, b"secret", b"aad")
    assert crypto.aead_decrypt(key, blob, b"aad") == b"secret"
    assert blob != crypto.aead_encrypt(key, b"secret", b"aad")  # fresh nonce
    bad = blob[:-1] + bytes([blob[-1] ^ 1])
    for args in ((key, bad, b"aad"), (key, blob, b"other"),
                 (crypto.random(32), blob, b"aad"), (key, blob[:10], b"aad")):
        with pytest.raises(crypto.CryptoError):
            crypto.aead_decrypt(*args)
