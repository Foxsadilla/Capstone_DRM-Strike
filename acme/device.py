# Name: device.py
# Nodes: Server, console. & cartridge (/opt/acme/acme/)
# Purpose: The device side's provisioning too
# Notes:
#   - init will generate kesy locally and write the signing request
#   - install will add certs (in the cartridge case, a whole image built)
#   - status will verify the image
# ===================================================================
# Libraries:

import os, sys, argparse
from pathlib import Path
from . import keystore as K
from .cert import CertError, Role
from .issuer import _print, describe

DEFAULT_HOME = "/var/lib/acme-device"

# ===================================================================
# MAIN

def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="acme-device")
    p.add_argument("--home", default=os.environ.get("ACME_DEVICE_HOME", DEFAULT_HOME))

    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init")
    s.add_argument("--role", required=True, choices=["server", "console"])
    s.add_argument("--model", required=True)
    s.add_argument("--csr-out", required=True)
    s = sub.add_parser("install")
    s.add_argument("dir")
    s.add_argument("--role", choices=["server", "console", "cartridge"], help="required when injecting a complete image")
    sub.add_parser("status")
    sub.add_parser("erase")
    a = p.parse_args(argv)
    img = K.DeviceImage(a.home)
    os.umask(0o077)
    try:
        if a.cmd == "init":
            csr = img.create(Role[a.role.upper()], a.model)
            out = Path(a.csr_out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(csr)
            print(f"serial={describe(csr)['serial']}")
        elif a.cmd == "install":
            src = Path(a.dir)
            if (src / "device.secret").exists():
                if not a.role:
                    raise K.KeystoreError("--role is required for injection")
                ident = img.inject(src, Role[a.role.upper()])
            else:
                ups = [(src / n).read_bytes() for n in K.UPDATE_CERTS
                       if img.role() is Role.CONSOLE]
                ident = img.install((src / "device.cert").read_bytes(), (src / "root.cert").read_bytes(), ups)
            print(f"installed serial={ident.cert.serial_hex} "
                  f"role={ident.cert.role.name.lower()}")
        elif a.cmd == "status":
            st = img.state()
            print(f"state: {st}")
            if st == "provisioned":
                ident = img.load(img.role())
                _print(describe(ident.cert.raw))
                print(f"  trust anchor  {ident.anchor.serial_hex}")
                print(f"  private keys  unlocked, match certificate" f" ({'sign+enc' if ident.enc_sk else 'sign'})")
                print(f"  update certs  {len(ident.update_certs)}")
        elif a.cmd == "erase":
            print("erased: " + ", ".join(img.erase()))
    except (K.KeystoreError, CertError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0

    # end

if __name__ == "__main__":
    sys.exit(main())