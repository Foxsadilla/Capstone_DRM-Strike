# Name: test_issuer.py
# Nodes: ALL (/tests/)
# Purpose: Testing the issuer aspect of Phase 0
# Notes:
#   - 
# ===================================================================

import json
import os

import cbor2
import pytest

from acme import cert as C
from acme import crypto, csr as R, issuer as I
from acme.cert import CertError, Role

NOW = 1_800_000_000


@pytest.fixture
def iss(tmp_path):
    i = I.Issuer(tmp_path / "home")
    i.init_root(7300, now=NOW)
    return i


def new_csr(role=Role.CARTRIDGE, model="CART-A1", serial=None):
    sk, _ = crypto.sign_keygen()
    enc = crypto.dh_keygen()[1] if role is Role.CONSOLE else None
    return R.make_csr(sk, serial=serial or crypto.random(16), role=role,
                      model=model, enc_pk=enc)


def test_root_files_and_permissions(iss):
    assert os.stat(iss.root_key).st_mode & 0o777 == 0o600
    anchor = C.load_trust_anchor(iss.root_cert.read_bytes(), now=NOW)
    assert anchor.sign_pk == crypto.sign_public(iss.root_key.read_bytes())
    assert [e["role"] for e in iss.issued()] == ["root"]


def test_root_is_never_overwritten(iss):
    before = iss.root_key.read_bytes()
    with pytest.raises(I.IssuerError):
        iss.init_root(7300, now=NOW)
    assert iss.root_key.read_bytes() == before


def test_update_keys(iss):
    certs = iss.init_update_keys(3650, now=NOW)
    anchor = C.load_trust_anchor(iss.root_cert.read_bytes(), now=NOW)
    assert [c.model for c in certs] == ["UPDATE-PRIMARY", "UPDATE-BACKUP"]
    keys = set()
    for name in ("primary", "backup"):
        raw = (iss.update_dir / f"{name}.cert").read_bytes()
        c = C.verify_cert(raw, anchor, Role.UPDATE, now=NOW)
        sk = (iss.update_dir / f"{name}.key").read_bytes()
        assert crypto.sign_public(sk) == c.sign_pk
        assert os.stat(iss.update_dir / f"{name}.key").st_mode & 0o777 == 0o600
        keys.add(sk)
    assert len(keys) == 2 and iss.root_key.read_bytes() not in keys
    assert iss.update_dir != iss.root_key.parent
    with pytest.raises(I.IssuerError):
        iss.init_update_keys(3650, now=NOW)


def test_update_keys_need_root(tmp_path):
    with pytest.raises(I.IssuerError):
        I.Issuer(tmp_path / "x").init_update_keys(10, now=NOW)


@pytest.mark.parametrize("role", R.REQUESTABLE)
def test_sign_roundtrip(iss, role):
    raw, entry = iss.sign_request(new_csr(role), 3650, now=NOW)
    anchor = C.load_trust_anchor(iss.root_cert.read_bytes(), now=NOW)
    c = C.verify_cert(raw, anchor, role, now=NOW)
    assert entry["serial"] == c.serial_hex and entry["role"] == role.name.lower()
    assert (c.enc_pk is not None) == (role is Role.CONSOLE)


def test_duplicate_serial_rejected(iss):
    s = crypto.random(16)
    iss.sign_request(new_csr(serial=s), 10, now=NOW)
    with pytest.raises(I.IssuerError):
        iss.sign_request(new_csr(serial=s), 10, now=NOW)


def test_device_validity_capped_by_root(iss):
    raw, e = iss.sign_request(new_csr(), 99999, now=NOW)
    assert e["not_after"] == NOW + 7300 * 86400


def _raw_csr(sk, over=None):
    body = {1: 1, 2: crypto.random(16), 3: int(Role.CARTRIDGE), 4: "CART-A1",
            5: crypto.sign_public(sk)}
    body.update(over or {})
    b = cbor2.dumps(body, canonical=True)
    return cbor2.dumps([b, crypto.sign(sk, R.SIG_CONTEXT + b)], canonical=True)


def test_cannot_request_privileged_roles(iss):
    sk, _ = crypto.sign_keygen()
    for role in (Role.ROOT, Role.UPDATE):
        with pytest.raises(CertError):
            iss.sign_request(_raw_csr(sk, {3: int(role)}), 10,
                             now=NOW)
        with pytest.raises(CertError):
            R.make_csr(sk, serial=crypto.random(16), role=role, model="X")


def test_csr_proof_of_possession(iss):
    sk, _ = crypto.sign_keygen()
    victim_pk = crypto.sign_keygen()[1]
    with pytest.raises(CertError) as e:
        iss.sign_request(_raw_csr(sk, {5: victim_pk}), 10, now=NOW)
    assert e.value.reason == "bad_signature"


@pytest.mark.parametrize("bad", [
    b"", b"junk", b"\x82\x40\x40",
    lambda sk: _raw_csr(sk, {7: 0}),          # validity is the issuer's call
    lambda sk: _raw_csr(sk, {9: bytes(16)}),
    lambda sk: _raw_csr(sk, {6: bytes(32)}),  # cartridge with enc key
    lambda sk: _raw_csr(sk) + b"\x00",
])
def test_malformed_csr(iss, bad):
    sk, _ = crypto.sign_keygen()
    raw = bad(sk) if callable(bad) else bad
    with pytest.raises(CertError):
        iss.sign_request(raw, 10, now=NOW)
    assert len(iss.issued()) == 1            # nothing logged on rejection


def test_sign_dir_and_manifest(iss, tmp_path):
    inbox, outbox = tmp_path / "in", tmp_path / "out"
    inbox.mkdir()
    (inbox / "a.csr").write_bytes(new_csr(Role.CONSOLE, "CONSOLE-X"))
    (inbox / "b.csr").write_bytes(new_csr(Role.SERVER, "SERVER-1"))
    (inbox / "c.csr").write_bytes(b"garbage")
    (inbox / "ignored.txt").write_bytes(b"x")
    ok, failed = iss.sign_dir(inbox, outbox, 3650, now=NOW)
    assert len(ok) == 2 and [f[0] for f in failed] == ["c.csr"]
    manifest = [json.loads(l) for l in
                (outbox / "manifest.jsonl").read_text().splitlines()]
    assert {m["role"] for m in manifest} == {"console", "server"}
    for m in manifest:
        assert (outbox / f"{m['serial']}.cert").exists()
    assert not list(outbox.glob("*.key"))


def test_export_public_has_no_private_keys(iss, tmp_path):
    iss.init_update_keys(3650, now=NOW)
    names = iss.export_public(tmp_path / "pub")
    assert sorted(names) == ["root.cert", "update-backup.cert",
                             "update-primary.cert"]
    secrets = [iss.root_key.read_bytes(),
               (iss.update_dir / "primary.key").read_bytes(),
               (iss.update_dir / "backup.key").read_bytes()]
    for f in (tmp_path / "pub").iterdir():
        assert not any(s in f.read_bytes() for s in secrets)


def test_loose_key_permissions_refused(iss):
    os.chmod(iss.root_key, 0o644)
    with pytest.raises(I.IssuerError):
        iss.sign_request(new_csr(), 10, now=NOW)


def test_air_gap_guard(monkeypatch):
    monkeypatch.setattr(I, "network_interfaces", lambda: ["eth0"])
    with pytest.raises(I.IssuerError):
        I.require_air_gap(False)
    I.require_air_gap(True)
    monkeypatch.setattr(I, "network_interfaces", lambda: [])
    I.require_air_gap(False)


def test_cli_end_to_end(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(I, "network_interfaces", lambda: [])
    home = str(tmp_path / "h")
    assert I.main(["--home", home, "init-root"]) == 0
    assert I.main(["--home", home, "init-root"]) == 2
    assert I.main(["--home", home, "init-update-keys"]) == 0
    inbox = tmp_path / "in"; inbox.mkdir()
    (inbox / "k.csr").write_bytes(new_csr())
    assert I.main(["--home", home, "sign", str(inbox), str(tmp_path / "o")]) == 0
    assert I.main(["--home", home, "export-public", str(tmp_path / "p")]) == 0
    assert I.main(["--home", home, "show", str(tmp_path / "p" / "root.cert"),
                   str(inbox / "k.csr")]) == 0
    assert I.main(["--home", home, "list"]) == 0
    out = capsys.readouterr().out
    assert "root" in out and "request" in out and "cartridge" in out
    monkeypatch.setattr(I, "network_interfaces", lambda: ["eth0"])
    assert I.main(["--home", home, "sign", str(inbox), str(tmp_path / "o")]) == 2