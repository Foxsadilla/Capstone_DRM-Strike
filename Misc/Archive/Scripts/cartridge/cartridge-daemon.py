#!/usr/bin/env python3
# Name: cartidge-daemon.py
# Nodes: cartridge (/opt/cartridge/cartridge_daemon.py)
# Purpose: Simulates the function of the cartridge
# Last Updated: 11/10/2026
# ==============================================

import os, subprocess, serial

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key

SERIAL_PORT = "/dev/ttyV0"
CARTRIDGE_ID = "storage-cartridge"
KEY_PATH = f"/etc/ssl/private/{CARTRIDGE_ID}.key"
LUKS_IMAGE = "/var/cartridge_storage.img"
MAPPER = "secure_cartridge"
MOUNT_POINT = "/mnt/cartridge_data"
OAEP = padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)

with open(KEY_PATH, "rb") as f:
    PRIVATE_KEY = load_pem_private_key(f.read(), password=None)

def sign_nonce(nonce_hex: str) -> str:
    return PRIVATE_KEY.sign(bytes.fromhex(nonce_hex), padding.PKCS1v15(), hashes.SHA256()).hex()
    # end

def unlock(key: bytes) -> str:
    if os.path.exists(f"/dev/mapper/{MAPPER}"):
        return "ALREADY_UNLOCKED"
    
    r = subprocess.run(["cryptsetup", "luksOpen", "--key-file=-", LUKS_IMAGE, MAPPER], input=key, capture_output=True)

    if r.returncode != 0:
        print("LuksOpem Faoled:", r.stderr.decode().strip())
        return "FAILED"
    os.makedirs(MOUNT_POINT, exist_ok=True)
    m = subprocess.run(["mount", f"/dev/mapper/{MAPPER}", MOUNT_POINT], capture_output=True)
    if m.returncode != 0:
        print("Mount failed:", m.stderr.decode().strip())
        subprocess.run(["cryptsetup", "luksClose", MAPPER])
        return "FAILED"
    return "UNLOCKED"
    # end

def lock() -> str:
    subprocess.run(["umount", MOUNT_POINT], capture_output=True)
    subprocess.run(["cryptsetup", "luksClose", MAPPER], capture_output=True)
    return "LOCKED"
    # end

def main():
    print(f"[*] Cartridge {CARTRIDGE_ID} listening on {SERIAL_PORT}")
    with serial.Serial(SERIAL_PORT, 115200, timeout=1) as ser:
        while True:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            try:
                if line == "ID?":
                    ser.write(f"ID:{CARTRIDGE_ID}\n".encode())
                elif line.startswith("CHALLENGE:"):
                    ser.write(f"SIGNATURE:{sign_nonce(line.split(':', 1)[1])}\n".encode())
                elif line.startswith("KEY:"):
                    key = PRIVATE_KEY.decrypt(bytes.fromhex(line.split(':', 1)[1]), OAEP)
                    ser.write(f"STATUS:{unlock(key)}\n".encode())
                elif line == "LOCK":
                    ser.write(f"STATUS:{lock()}\n".encode())
            except Exception as e:
                print("[-] error:", e)
                ser.write(b"STATUS:ERROR\n")
    # end

if __name__ == "__main__":
    main()