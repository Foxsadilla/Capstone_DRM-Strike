# Name: issuer.py
# Nodes: host (i.e., pve4) (/opt/a cme/acme/)
# Purpose: Functions as the issuer for ACME psuedo offline factory
# Notes:
#   - State directory:
#       - root/root.key issuing key
#       - root/root.cert Cert_ACME
#       - update/primary.*   update-signing key + cert (role update)
#       - update/backup.* backup update key + cert  (role update)
#       - issued.jsonl  one line per certificate ever issued
# ===================================================================
# Libraries:

import argparse, hashlib, json, os, sys, time
from pathlib import Path

from . import cert as C
from . import crypto
from . import csr as R
from .cert import CertError, Role

DAY = 86400
DEFAULT_HOME = "/var/lib/acme-issuer"

class IssueError(Exception):
    pass

# ===================================================================
# Emulated Air-gapped environment:

def network_interfaces() -> list[str]:
    try:
        return sorted(n for n in os.listdir("/sys/class/net") if n != "lo")
    except OSError:
        return[]
    # end

def require_air_gap(allow_network: bool) -> None:
    nics = network_interfaces()
    if not nics:
        return
    msg = f"Network interfece(s) currently present: {','.join(nics)}"
    if not allow_network:
        raise IssueError(msg + " > The issuer needs to be air-gapped; remove the interface or bypass by adding: --allow-network")
        
    print(f"UPDATE: {msg}; Now continuing because of the inclusion of --allow-network", file=sys.stderr)
    # end


# ===================================================================
# Storage:

def _write_new(path: Path, data: bytes, mode: int) -> None:
    # Creaes a file that will not overwrite a pre-existing one
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    # end

def _read_key(path: Path) -> bytes:
    if path.stat().st_mode & 0o077:
        raise IssueError(f"{path} is readable by other, fix it's permissions!")
    key = path.read_bytes()
    if len(key) != crypto.SIGN_PK_LEN:
        raise IssueError(f"{path} is not a valid key file...")
    return key
    # end

# Issuer template:
class Issuer:
    def __init__(self, home):
        self.home = Path(home)
        self.root_key = self.home / "root" / "root.key"
        self.root_cert = self.home / "root" / "root.cert"
        self.update_dir = self.home / "update"
        self.log = self.home / "issued.jsonl"

    # Issued log:
    def issued(self) -> list[dict]:
        if not self.log.exists():
            return []
        return [json.loads(l) for l in self.log.read_text().splitlines() if l]
        # end

    def _record(self, raw: butes, c: C.Certificate) -> dict:
        entry = {"serial": c.serial_hex, "role": c.role.name.lower(),
                 "model": c.model, "not_before": c.not_before,
                 "not_after": c.not_after, "issued_at": int(time.time()),
                 "cert_sha256": hashlib.sha256(raw).hexdigest()}
        self.home.mkdir(mode=0o700, parents=True, exist_ok=True)
        with open(self.log, "a") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return entry
        # end

    def _fresh_serial(self) -> bytes:
        used = {e["serial"] for e in self.issued()}
        while True:
            s = crypto.random(C.SERIAL_LEN)
            if s.hex() not in used:
                return s
        # end

    def _anchor(self, now=None) -> C.Certificate:
        if not self.root_cert.exists():
            raise IssueError("no root yet! run init-root")
        return C.load_trust_anchor(self.root_cert.read_bytes(), now=now)
        # end

    # Generate the root:
    def init_root(self, days: int, now=None) -> C.Certificate:
        if self.root_key.exists() or self.root_cert.exists():
            raise IssueError("Root already exists, will not overwrite")
        now = int(time.time()) if now is None else now
        sk, _ = crypto.sign_keygen()
        raw = C.issue_root(sk, serial=self._fresh_serial(), not_before=now, not_after=now + days * DAY)
        anchor = C.load_trust_anchor(raw, now=now)
        _write_new(self.root_key, sk, 0o600)
        _write_new(self.root_cert, raw, 0o644)
        self._record(raw, anchor)
        return anchor
        # end

    # Update the keys:
    def init_update_keys(self, days: int, now=None) -> list[C.Certificate]:
        now = int(time.time()) if now is None else now
        anchor = self._anchor(now)
        root_sk = _read_key(self.root_key)
        names = {"primary", "backup"}
        if any((self.update_dir / f"{n}.key").exists() for n in names):
            raise IssueError("Update kesy already exist; not overwriting.")
        out = []

        for name in names:
            sk, pk = crypto.sign_keygen()
            raw = C.issue_cert(root_sk, anchor.serial, serial=self._fresh_serial(), role=Role.UPDATE, model=f"UPDATE-{name.upper()}", sign_pk=pk, not_before=now, not_after=now + days * DAY)
            c = C.verify_cert(raw, anchor, Role.UPDATE, now=now)
            _write_new(self.update_dir / f"{name}.key", sk, 0o600)
            _write_new(self.update_dir / f"{name}.cert", raw, 0o644)
            self._record(raw, c)
            out.append(c)
        return out
        # end

    # Issue the certficates:
    def sign_request(self, csr_raw: bytes, days: int, now=None) -> tuple[bytes, dict]:
        now = int(time.time()) if now is None else now
        anchor = self._anchor(now)
        req = R.parse_csr(csr_raw)
        log = self.issued()
        if any(e["serial"] == req.serial.hex() for e in log):
            raise IssueError(f"serial {req.serial.hex()} was already issued")
        not_after = min(now + days * DAY, anchor.not_after)
        raw = C.issue_cert(_read_key(self.root_key), anchor.serial,
                           serial=req.serial, role=req.role, model=req.model,
                           sign_pk=req.sign_pk, enc_pk=req.enc_pk,
                           not_before=now, not_after=not_after)
        c = C.verify_cert(raw, anchor, req.role, now=now)
        return raw, self._record(raw, c)
        # end

    def sign_dir(self, inbox, outbox, days: int, now=None):
        inbox, outbox = Path(inbox)
        
        # end

    def export_public(self, dest) -> list[str]:
        # end

# ===================================================================
# Description Display

def describe(raw: bytes) -> dict:
    # end

def _print(d: dict) -> None:
    # end

# ===================================================================
# CLI print ou tof the issueing process for reference
def main(argv=None) -> int:
    # end

if __name__ == "__main__":
    sys.exit(main())