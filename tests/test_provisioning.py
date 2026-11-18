# Name: test_provisioning.py
# Nodes: ALL (/tests/)
# Purpose: Testing the provisioning aspect of Phase 0
# Notes:
#   - 
# ===================================================================

import os

import pytest

from acme import cert as C
from acme import crypto, issuer as I, keystore as K, registry as G, station as S
from acme.cert import CertError, Role

NOW = 1_800_000_000


@pytest.fixture
def world(tmp_path):
    iss = I.Issuer(tmp_path / "issuer")
    iss.init_root(7300, now=NOW)
    iss.init_update_keys(3650, now=NOW)
    pub = tmp_path / "pub"
    iss.export_public(pub)
    st = S.Station(tmp_path / "station")
    st.trust(pub, now=NOW)
    return iss, st, tmp_path


def sign_round(iss, st, tmp, n=[0]):
    n[0] += 1
    a, b = tmp / f"req{n[0]}", tmp / f"crt{n[0]}"
    st.export_requests(a)
    ok, failed = iss.sign_dir(a, b, 3650, now=NOW)
    assert not failed
    done, failed = st.receive(b, now=NOW)
    assert not failed
    return done


def provision_self_keyed(world, role, name):
    iss, st, tmp = world
    img = K.DeviceImage(tmp / name)
    req = st.accept(img.create(role, f"{name.upper()}-1"))
    sign_round(iss, st, tmp)
    out = tmp / f"{name}-in"
    st.export(req.serial.hex(), out)
    ups = [(out / n).read_bytes() for n in K.UPDATE_CERTS] \
        if role is Role.CONSOLE else []
    ident = img.install((out / "device.cert").read_bytes(),
                        (out / "root.cert").read_bytes(), ups, now=NOW)
    return img, ident


def provision_cartridge(world, name="cart"):
    iss, st, tmp = world
    req = st.new_cartridge("CART-A1")
    sign_round(iss, st, tmp)
    out = tmp / f"{name}-in"
    st.export(req.serial.hex(), out)
    img = K.DeviceImage(tmp / name)
    ident = img.inject(out, Role.CARTRIDGE, now=NOW)
    st.erase(req.serial.hex())
    return img, ident


# --- key storage ----------------------------------------------------------
def test_console_image(world):
    img, ident = provision_self_keyed(world, Role.CONSOLE, "console")
    assert ident.cert.role is Role.CONSOLE and ident.enc_sk
    assert crypto.sign_public(ident.sign_sk) == ident.cert.sign_pk
    assert crypto.dh_public(ident.enc_sk) == ident.cert.enc_pk
    assert ident.sign_sk != ident.enc_sk
    assert len(ident.update_certs) == 2
    assert img.state() == "provisioned"
    assert not (img.home / "request.csr").exists()
    again = img.load(Role.CONSOLE, now=NOW)
    assert again.sign_sk == ident.sign_sk


def test_server_image_has_no_enc_key_or_update_certs(world):
    img, ident = provision_self_keyed(world, Role.SERVER, "server")
    assert ident.enc_sk is None and ident.update_certs == ()
    assert not (img.home / "enc.key.enc").exists()
    assert not (img.home / "update-primary.cert").exists()


def test_private_keys_not_stored_in_clear(world):
    img, ident = provision_self_keyed(world, Role.CONSOLE, "console")
    for f in img.home.iterdir():
        data = f.read_bytes()
        assert ident.sign_sk not in data and ident.enc_sk not in data
    for n in K.SECRET_FILES:
        assert os.stat(img.home / n).st_mode & 0o777 == 0o600


def test_wrong_device_secret_or_tamper_fails(world):
    img, _ = provision_self_keyed(world, Role.CONSOLE, "console")
    p = img.home / "device.secret"
    good = p.read_bytes()
    p.write_bytes(crypto.random(32))
    with pytest.raises(K.KeystoreError):
        img.load(Role.CONSOLE, now=NOW)
    p.write_bytes(good)
    k = img.home / "sign.key.enc"
    blob = bytearray(k.read_bytes()); blob[-1] ^= 1; k.write_bytes(bytes(blob))
    with pytest.raises(K.KeystoreError):
        img.load(Role.CONSOLE, now=NOW)


def test_key_blobs_are_bound_to_device_and_purpose(world):
    a, _ = provision_self_keyed(world, Role.CONSOLE, "console")
    b, _ = provision_self_keyed(world, Role.CONSOLE, "console2")
    # another console's key files (and its secret) do not load under our cert
    for n in ("device.secret", "sign.key.enc", "enc.key.enc"):
        (a.home / n).write_bytes((b.home / n).read_bytes())
    with pytest.raises(K.KeystoreError):
        a.load(Role.CONSOLE, now=NOW)
    # swapping sign and enc blobs within one device fails too
    s, e = (b.home / "sign.key.enc"), (b.home / "enc.key.enc")
    sb, eb = s.read_bytes(), e.read_bytes()
    s.write_bytes(eb); e.write_bytes(sb)
    with pytest.raises(K.KeystoreError):
        b.load(Role.CONSOLE, now=NOW)


def test_load_checks_role_and_expiry(world):
    img, _ = provision_self_keyed(world, Role.SERVER, "server")
    with pytest.raises(K.KeystoreError):
        img.load(Role.CONSOLE, now=NOW)
    (img.home / "role").write_text("console\n")
    with pytest.raises(CertError):
        img.load(Role.CONSOLE, now=NOW)
    (img.home / "role").write_text("server\n")
    with pytest.raises(CertError):
        img.load(Role.SERVER, now=NOW + 4000 * 86400)


def test_install_rejects_foreign_cert_and_foreign_root(world):
    iss, st, tmp = world
    a = K.DeviceImage(tmp / "a"); ra = st.accept(a.create(Role.SERVER, "S"))
    b = K.DeviceImage(tmp / "b"); rb = st.accept(b.create(Role.SERVER, "S"))
    sign_round(iss, st, tmp)
    root = (st.trust_dir / "root.cert").read_bytes()
    cert_b = (st.certs / f"{rb.serial.hex()}.cert").read_bytes()
    with pytest.raises(K.KeystoreError):
        a.install(cert_b, root, now=NOW)
    assert a.state() == "pending" and not (a.home / "device.cert").exists()
    other = I.Issuer(tmp / "evil"); other.init_root(10, now=NOW)
    cert_a = (st.certs / f"{ra.serial.hex()}.cert").read_bytes()
    with pytest.raises(CertError):
        a.install(cert_a, other.root_cert.read_bytes(), now=NOW)
    a.install(cert_a, root, now=NOW)


def test_console_requires_two_distinct_update_certs(world):
    iss, st, tmp = world
    img = K.DeviceImage(tmp / "c"); r = st.accept(img.create(Role.CONSOLE, "C"))
    sign_round(iss, st, tmp)
    root = (st.trust_dir / "root.cert").read_bytes()
    cert = (st.certs / f"{r.serial.hex()}.cert").read_bytes()
    up = (st.trust_dir / "update-primary.cert").read_bytes()
    for ups in ([], [up], [up, up], [up, cert]):
        with pytest.raises((K.KeystoreError, CertError)):
            img.install(cert, root, ups, now=NOW)
    assert img.state() == "pending"


def test_image_cannot_be_recreated(world):
    img, _ = provision_self_keyed(world, Role.SERVER, "server")
    with pytest.raises(K.KeystoreError):
        img.create(Role.SERVER, "S")


# --- station --------------------------------------------------------------
def test_cartridge_flow_and_station_erasure(world):
    iss, st, tmp = world
    img, ident = provision_cartridge(world)
    assert ident.cert.role is Role.CARTRIDGE and ident.enc_sk is None
    assert ident.update_certs == ()
    assert not (st.work / ident.cert.serial_hex).exists()
    assert list(st.work.iterdir()) == []
    # the station keeps the public certificate only
    for f in st.home.rglob("*"):
        if f.is_file():
            assert ident.sign_sk not in f.read_bytes()
            assert f.name not in K.SECRET_FILES
    with pytest.raises(S.StationError):
        st.erase(ident.cert.serial_hex)


def test_station_refuses_device_made_cartridge_request(world):
    iss, st, tmp = world
    from acme import csr as R
    sk, _ = crypto.sign_keygen()
    raw = R.make_csr(sk, serial=crypto.random(16), role=Role.CARTRIDGE,
                     model="CART")
    with pytest.raises(S.StationError):
        st.accept(raw)


def test_station_rejects_cert_from_wrong_issuer(world):
    iss, st, tmp = world
    img = K.DeviceImage(tmp / "s"); st.accept(img.create(Role.SERVER, "S"))
    evil = I.Issuer(tmp / "evil"); evil.init_root(10, now=NOW)
    st.export_requests(tmp / "r")
    evil.sign_dir(tmp / "r", tmp / "c", 10, now=NOW)
    done, failed = st.receive(tmp / "c", now=NOW)
    assert done == [] and len(failed) == 1
    assert list(st.certs.glob("*.cert")) == []


def test_station_trust_cannot_be_swapped(world):
    iss, st, tmp = world
    evil = I.Issuer(tmp / "evil")
    evil.init_root(10, now=NOW); evil.init_update_keys(10, now=NOW)
    evil.export_public(tmp / "evilpub")
    with pytest.raises(S.StationError):
        st.trust(tmp / "evilpub", now=NOW)


def test_inject_bad_image_leaves_nothing(world):
    iss, st, tmp = world
    req = st.new_cartridge("CART-A1")
    sign_round(iss, st, tmp)
    out = tmp / "img"
    st.export(req.serial.hex(), out)
    (out / "device.secret").write_bytes(crypto.random(32))
    img = K.DeviceImage(tmp / "cart")
    with pytest.raises(K.KeystoreError):
        img.inject(out, Role.CARTRIDGE, now=NOW)
    assert img.state() == "empty" and list(img.home.iterdir()) == []


def test_unique_identities(world):
    idents = [provision_cartridge(world, f"cart{i}")[1] for i in range(3)]
    assert len({i.cert.serial for i in idents}) == 3
    assert len({i.sign_sk for i in idents}) == 3


# --- registry -------------------------------------------------------------
def test_registry(world):
    iss, st, tmp = world
    _, server = provision_self_keyed(world, Role.SERVER, "server")
    _, console = provision_self_keyed(world, Role.CONSOLE, "console")
    _, cart = provision_cartridge(world)
    reg = G.Registry(tmp / "srv" / "registry.db")
    anchor = server.anchor
    for ident in (server, console, cart):
        assert reg.register_cert(ident.cert.raw, anchor, now=NOW) == "new"
    assert reg.register_cert(cart.cert.raw, anchor, now=NOW) == "known"
    rows = {r["serial"]: r for r in reg.all()}
    assert len(rows) == 3
    r = rows[console.cert.serial_hex]
    assert (r["role"], r["status"], r["registered_at"]) == ("console", "active", NOW)
    assert reg.is_active(cart.cert.serial)
    assert not reg.is_active(crypto.random(16))
    # persists
    assert len(G.Registry(tmp / "srv" / "registry.db").all()) == 3


def test_registry_rejects_unsigned_and_root(world):
    iss, st, tmp = world
    reg = G.Registry(":memory:")
    anchor = st.anchor(now=NOW)
    evil = I.Issuer(tmp / "evil"); evil.init_root(10, now=NOW)
    evil.init_update_keys(10, now=NOW)
    with pytest.raises(CertError):
        reg.register_cert((evil.update_dir / "primary.cert").read_bytes(),
                          anchor, now=NOW)
    with pytest.raises(CertError):
        reg.register_cert(anchor.raw, anchor, now=NOW)
    with pytest.raises(CertError):
        reg.register_cert(b"junk", anchor, now=NOW)
    assert reg.all() == []
