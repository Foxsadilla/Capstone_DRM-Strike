# Name: registry.py
# Nodes: server (/opt/acme/acme/)
# Purpose: server-side device registry
# Notes:
#   - Creates one row per each serial issued: roles, model, status and timestamps.
#   - Devices become reigstered from its cert after verification from the cert first
#   - The registry will never trust an unsigned list
# ===================================================================
# Libraries & Templates

import argparse, hashlib, os, sqlite3, sys, time
from pathlib import Path
from . import cert as C
from .cert import CertError, Role

DEFAULT_DB = "/var/lib/acme-server/registry.db"
DEFAULT_ROOT = "/var/lib/acme-device/root.cert"
REGISTERED_ROLES =  (Role.SERVER, Role.CONSOLE, Role.CARTRIDGE, Role.UPDATE)
SCHEME = """
CREATE TABLE IF NOT EXISTS devices (
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
"""

class RegError(Exception):
    pass

class Registry:
    def __init__(self, db_path):
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(db_path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEME)

    def register_cert(self, raw: bytes, anchor: C.Certificate, now=None) -> str:
        # Verify a cert and record it, returining new or known
        now = int(time.time()) if now is None else now
        cert = None
        for role in REGISTERED_ROLES:
            try:
                cert = C.verify_cert(raw, anchor, role, now=now)
                break
            except  CertError as e:
                if e.reason != "wrong_role":
                    raise
        if cert is None:            
            raise CertError("wrong_role", "Not a registrable role.")
        digest = hashlib.sha256(raw).hexdigest()
        row = self.get(cert.serial_hex)
        if row is not None:
            if row["cert_sha256"] != digest:
                raise RegError(
                    f"serial {cert.serial_hex} is already registered with a "
                    "different certificate")
            return "known"
        with self.db:
            self.db.execute(
                "INSERT INTO devices VALUES (?,?,?,'active',?,?,?,?,?)",
                (cert.serial_hex, cert.role.name.lower(), cert.model, digest,
                 cert.not_before, cert.not_after, now, now))
        return "new"
        # end

    def get(self, serial_hex: str):
        return self.db.execute("SELECT * FROM devices WHERE serial = ?", (serial_hex,)).fetchone()
        # end

    def is_active(self, serial: bytes) -> bool:
        row = self.get(serial.hex())
        return row is not None and row["status"] == "active"
        # end

    def all(self):
        return self.db.execute("SELECT * FROM devices ORDER BY registered_at, serial").fetchall()
        # end

# ===================================================================
# Main:

def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="acme-registry")
    p.add_argument("--db", default=os.environ.get("ACME_REGISTRY_DB", DEFAULT_DB))
    p.add_argument("--root", default=os.environ.get("ACME_ROOT_CERT", DEFAULT_ROOT))
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("import", help="register every *.cert in DIR")
    s.add_argument("dir")
    sub.add_parser("list")
    a = p.parse_args(argv)
    os.umask(0o077)
    try:
        reg = Registry(a.db)
        if a.cmd == "import":
            anchor = C.load_trust_anchor(Path(a.root).read_bytes())
            bad = 0
            for f in sorted(Path(a.dir).glob("*.cert")):
                try:
                    print(f"{reg.register_cert(f.read_bytes(), anchor):<6}" f" {f.name}")
                except (CertError, RegError) as e:
                    bad += 1
                    print(f"REJECTED {f.name}: {e}", file=sys.stderr)
            return 1 if bad else 0
        for r in reg.all():
            t = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime(r["registered_at"]))
            print(f"{r['serial']}  {r['role']:<9} {r['model']:<16} " f"{r['status']:<8} {t}")
    except (CertError, RegError, OSError, sqlite3.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0
    # end

if __name__ == "__main__":
    sys.exit(main())