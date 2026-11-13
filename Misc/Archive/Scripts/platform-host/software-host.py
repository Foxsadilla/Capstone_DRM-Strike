#!/usr/bin/env python3
# Name: software-host.py
# Nodes: platform/software-host 
# Purpose: Simulates the function of dedicated software
# Last Updated: 11/10/2026
# ==============================================

import sys, requests, serial

SERVER = "https://172.16.10.114"
HOST_SERIAL = "HOST-SERIAL-001"
SERIAL_PORT = "/dev/ttyS_CARTRIDGE"
CERT = ("/etc/cartridge/HOST-SERIAL-001.crt", "/etc/cartridge/HOST-SERIAL-001.key")
CA = "/etc/cartridge/ca.crt"

def exchange(ser, line, prefix):
    ser.reset_input_buffer()
    ser.write((line + "\n").encode())
    reply = ser.readline().decode("utf-8", errors="ignore").strip()
    if not reply.startswith(prefix):
        raise RuntimeError(f"unexpected cartridge reply to {line[:12]!r}: {reply!r}")
    return reply[len(prefix):]
    # end

def post(path, payload):
    r = requests.post(f"{SERVER}{path}", json=payload, cert=CERT, verify=CA, timeout=5)
    if r.status_code != 200:
        raise RuntimeError(f"server rejected {path}: {r.status_code} {r.text.strip()}")
    return r.json()
    # end

def main():
    with serial.Serial(SERIAL_PORT, 115200, timeout=5) as ser:
        cartridge_id = exchange(ser, "ID?", "ID:")
        print(f"> Cartridge reports ID {cartridge_id}")

        nonce = post("/api/challenge", {"host_serial": HOST_SERIAL, "cartridge_id": cartridge_id})["nonce"]
        print("> Challenge received")

        signature = exchange(ser, f"CHALLENGE:{nonce}", "SIGNATURE:")
        print("> Cartridge signed the challenge")

        wrapped = post("/api/unlock", {"nonce": nonce, "signature": signature})["wrapped_key"]
        print("> Server verified cartridge and released wrapped key")

        ser.timeout = 30                      # LUKS key derivation can take a few seconds
        status = exchange(ser, f"KEY:{wrapped}", "STATUS:")
        print(f"> Cartridge status: {status}")
        sys.exit(0 if status in ("UNLOCKED", "ALREADY_UNLOCKED") else 1)
    # end

if __name__ == "__main__":
    main()