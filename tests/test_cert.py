# Name: test_cert.py
# Nodes: ALL (/tests/)
# Purpose: Testing the cert aspect of Phase 0
# Notes:
#   - Verify valid certs pass verfication (e.g., 16 byte serial num)
#   - Test that a cert is valid within its boundary timestamps
#   - Test that a cert will be rejected if it was signed by a forgien private key
#   - Test that a valid device cert cannot act as a CA to sign other device certs
#   - Test flipping a bit inside a cert payload to cause verification failure
#   - Test flipping a bit in the signature byte to cause a failure
#   - Test rejecting a cert is its embedded issuer serial num does not match the trusted root's
#   - Test that signtures are rejected if they were genereted without the SIG_CONTEXT
#   - Test that certs are rejected if their role does not match the one expected by server
#   - Test that the root cert will not be passed as a device cert
#   - Test expected roles by type error
#   -  
# ===================================================================
import cbor2
import pytest

from acme import cert as C
from acme import crypto
from acme.cert import CertError, Role

NOW = 1_800_000_000
DAY = 86400

# ===================================================================
# Test Cert

@pytest.fixture(scope="module")
def root():
    sk, _ = crypto.sign_keygen()
    serial = crypto.random(16)
    raw = C.issue_root(sk, serial=serial, not_before=NOW - DAY,
                       not_after=NOW + 3650 * DAY)
    return sk, C.load_trust_anchor(raw, now=NOW)


def make(root, role=Role.CARTRIDGE, **kw):
    sk, anchor = root
    args = dict(serial=crypto.random(16), role=role, model="CART-A1",
                sign_pk=crypto.sign_keygen()[1],
                not_before=NOW - DAY, not_after=NOW + 365 * DAY)
    if role is Role.CONSOLE:
        args["enc_pk"] = crypto.dh_keygen()[1]
    args.update(kw)
    return C.issue_cert(kw.pop("_sk", sk), kw.pop("_iss", anchor.serial),
                        **{k: v for k, v in args.items() if not k.startswith("_")})


def forge(root, mutate, sk=None):
    """Sign an arbitrary (possibly invalid) tbs with the real root key."""
    rsk, anchor = root
    tbs = {1: 1, 2: crypto.random(16), 3: int(Role.CARTRIDGE), 4: "CART-A1",
           5: crypto.sign_keygen()[1], 7: NOW - DAY, 8: NOW + DAY,
           9: anchor.serial}
    out = mutate(tbs)
    tbs_bytes = out if isinstance(out, bytes) else cbor2.dumps(tbs, canonical=True)
    sig = crypto.sign(sk or rsk, C.SIG_CONTEXT + tbs_bytes)
    return cbor2.dumps([tbs_bytes, sig], canonical=True)


def reject(raw, anchor, role, reason, **kw):
    with pytest.raises(CertError) as e:
        C.verify_cert(raw, anchor, role, now=kw.pop("now", NOW), **kw)
    assert e.value.reason == reason


# ===================================================================
# Accepted

@pytest.mark.parametrize("role", [Role.SERVER, Role.CONSOLE, Role.CARTRIDGE,
                                  Role.UPDATE])
def test_valid_cert_each_role(root, role):
    raw = make(root, role)
    c = C.verify_cert(raw, root[1], role, now=NOW)
    assert c.role is role and c.raw == raw and len(c.serial) == 16
    assert (c.enc_pk is not None) == (role is Role.CONSOLE)
    assert len(raw) <= C.MAX_CERT_LEN


def test_validity_edges_inclusive(root):
    raw = make(root, not_before=NOW, not_after=NOW)
    C.verify_cert(raw, root[1], Role.CARTRIDGE, now=NOW)


# ===================================================================
# Wrong signer
def test_wrong_signer(root):
    other_sk, _ = crypto.sign_keygen()
    reject(make(root, _sk=other_sk), root[1], Role.CARTRIDGE, "bad_signature")


def test_signed_by_another_device_not_root(root):
    dev_sk, dev_pk = crypto.sign_keygen()
    make(root, sign_pk=dev_pk)
    reject(make(root, _sk=dev_sk), root[1], Role.CARTRIDGE, "bad_signature")


def test_tampered_body(root):
    raw = bytearray(make(root))
    raw[20] ^= 1
    with pytest.raises(CertError):
        C.verify_cert(bytes(raw), root[1], Role.CARTRIDGE, now=NOW)


def test_tampered_signature(root):
    raw = bytearray(make(root))
    raw[-1] ^= 1
    reject(bytes(raw), root[1], Role.CARTRIDGE, "bad_signature")


def test_issuer_serial_mismatch(root):
    reject(make(root, _iss=crypto.random(16)), root[1], Role.CARTRIDGE,
           "bad_signature")


# ===================================================================
# Wrong role

@pytest.mark.parametrize("have,want", [
    (Role.CARTRIDGE, Role.CONSOLE), (Role.CARTRIDGE, Role.SERVER),
    (Role.CONSOLE, Role.SERVER), (Role.SERVER, Role.UPDATE),
    (Role.UPDATE, Role.CONSOLE)])
def test_wrong_role(root, have, want):
    reject(make(root, have), root[1], want, "wrong_role")


def test_root_cert_is_not_a_device(root):
    reject(root[1].raw, root[1], Role.SERVER, "wrong_role")


def test_expected_role_is_mandatory(root):
    with pytest.raises(TypeError):
        C.verify_cert(make(root), root[1])
    with pytest.raises(ValueError):
        C.verify_cert(make(root), root[1], Role.ROOT, now=NOW)
    with pytest.raises(ValueError):
        C.verify_cert(make(root), root[1], 3, now=NOW)


# ===================================================================
# Valdiity

def test_expired(root):
    raw = make(root, not_before=NOW - 2 * DAY, not_after=NOW - 1)
    reject(raw, root[1], Role.CARTRIDGE, "expired")


def test_not_yet_valid(root):
    raw = make(root, not_before=NOW + 1, not_after=NOW + DAY)
    reject(raw, root[1], Role.CARTRIDGE, "not_yet_valid")


def test_revoked(root):
    raw = make(root)
    serial = C.verify_cert(raw, root[1], Role.CARTRIDGE, now=NOW).serial
    reject(raw, root[1], Role.CARTRIDGE, "revoked",
           is_revoked=lambda s: s == serial)
    C.verify_cert(raw, root[1], Role.CARTRIDGE, now=NOW,
                  is_revoked=lambda s: False)


# ===================================================================
# Malformed

@pytest.mark.parametrize("raw", [
    b"", b"\x00", b"not cbor at all", b"\xff" * 40, b"\x82\x40",
    b"A" * (C.MAX_CERT_LEN + 1)])
def test_garbage(root, raw):
    reject(raw, root[1], Role.CARTRIDGE, "malformed")


def test_non_bytes_input(root):
    reject("text", root[1], Role.CARTRIDGE, "malformed")


def test_truncated_and_trailing(root):
    raw = make(root)
    for n in (1, 10, len(raw) // 2, len(raw) - 1):
        reject(raw[:n], root[1], Role.CARTRIDGE, "malformed")
    reject(raw + b"\x00", root[1], Role.CARTRIDGE, "malformed")


MUTATIONS = {
    "unknown_field": lambda t: t.update({10: 1}),
    "text_key": lambda t: t.update({"x": 1}),
    "missing_serial": lambda t: t.pop(2),
    "missing_role": lambda t: t.pop(3),
    "missing_validity": lambda t: t.pop(8),
    "bad_version": lambda t: t.update({1: 2}),
    "short_serial": lambda t: t.update({2: b"\x01" * 15}),
    "serial_as_text": lambda t: t.update({2: "0123456789abcdef"}),
    "unknown_role": lambda t: t.update({3: 9}),
    "role_as_bool": lambda t: t.update({3: True}),
    "role_as_text": lambda t: t.update({3: "cartridge"}),
    "empty_model": lambda t: t.update({4: ""}),
    "long_model": lambda t: t.update({4: "M" * 33}),
    "short_sign_pk": lambda t: t.update({5: b"\x01" * 31}),
    "negative_time": lambda t: t.update({7: -1}),
    "inverted_window": lambda t: t.update({7: NOW + DAY, 8: NOW}),
    "cartridge_with_enc_pk": lambda t: t.update({6: b"\x01" * 32}),
    "console_without_enc_pk": lambda t: t.update({3: int(Role.CONSOLE)}),
    "console_short_enc_pk": lambda t: t.update({3: int(Role.CONSOLE),
                                                6: b"\x01" * 31}),
    "tbs_not_a_map": lambda t: cbor2.dumps([1, 2, 3]),
    "tbs_not_cbor": lambda t: b"\xff\xff\xff",
    "tbs_trailing_bytes": lambda t: cbor2.dumps(t, canonical=True) + b"\x00",
    # serial length encoded with a 1-byte length prefix instead of inline
    "non_deterministic": lambda t: cbor2.dumps(t, canonical=True).replace(
        b"\x02\x50", b"\x02\x58\x10", 1),
}


@pytest.mark.parametrize("name", MUTATIONS)
def test_correctly_signed_but_malformed(root, name):
    """Even with a genuine ACME signature, a bad body must be rejected."""
    reject(forge(root, MUTATIONS[name]), root[1], Role.CARTRIDGE, "malformed")


def test_issuer_refuses_to_sign_bad_fields(root):
    with pytest.raises(CertError):
        make(root, Role.CARTRIDGE, enc_pk=b"\x01" * 32)
    with pytest.raises(CertError):
        make(root, Role.CONSOLE, enc_pk=None)
    with pytest.raises(CertError):
        make(root, serial=b"short")


def test_envelope_shapes(root):
    sk, anchor = root
    tbs = cbor2.loads(make(root))[0]
    sig = crypto.sign(sk, C.SIG_CONTEXT + tbs)
    for env in ([tbs], [tbs, sig, sig], [tbs, sig[:63]], {1: tbs, 2: sig},
                [sig, tbs]):
        reject(cbor2.dumps(env, canonical=True), anchor, Role.CARTRIDGE,
               "malformed")


def test_signature_context_binds(root):
    """A signature over the bare tbs (no context prefix) is not a cert."""
    sk, anchor = root
    tbs = cbor2.loads(make(root))[0]
    raw = cbor2.dumps([tbs, crypto.sign(sk, tbs)], canonical=True)
    reject(raw, anchor, Role.CARTRIDGE, "bad_signature")


# ===================================================================
# Trust Anchor

def test_anchor_rejects_non_root_and_corruption(root):
    sk, anchor = root
    with pytest.raises(CertError):
        C.load_trust_anchor(make(root, Role.SERVER), now=NOW)
    bad = bytearray(anchor.raw)
    bad[-1] ^= 1
    with pytest.raises(CertError):
        C.load_trust_anchor(bytes(bad), now=NOW)
    with pytest.raises(CertError):
        C.load_trust_anchor(anchor.raw, now=NOW + 4000 * DAY)


def test_device_cert_cannot_act_as_anchor(root):
    with pytest.raises(ValueError):
        C.verify_cert(make(root), C.verify_cert(make(root), root[1],
                      Role.CARTRIDGE, now=NOW), Role.CARTRIDGE, now=NOW)