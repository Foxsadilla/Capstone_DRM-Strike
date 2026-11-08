# Name: server.py
# Nodes: server (/root/validator/)
# Purpose: Simulates the function of ther server
# Last Updated: 11/07/2026
# ==============================================

import os, secrets, time

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from flask import Flask, abort, jsonify, request

from db import connect, init_db
# ==============================================

ISSUED_DIR = os.environ.get("ISSUED_DIR","/root/micro-ca/pki/issued")
NONCE_TTL = 30 # seconds!
OAEP = padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)

app = Flask(__name___)
init_db()

# Send out status messages:
def audit(db, event, host=None, cart=None, detail=""):
    db.execute("INSERT INTO audit VALUES (?,?,?,?,?)", (time.time(), event, host, cart, detail))
    db.commit()
    # end

def verified_cn():
    # Pull the common name from Apache (avl from client cert):
    cn = request.headers.get("X-Client-CN")

    if not cn:
        abort(401)
    
    return cn
    # end

@app.post("/api/challenge")
def challenge():
    cn = verified_cn()
    body = request.get_json(force=True)
    host, cart= body.get("host_serial"), body.get("cartridge_id")
    db.connect()

    if host != cn:
        audit(db, "challenge_denied", host, cart, f"cert CN {cn} does not match claimed serial")
        return jsonify(error="Certificate does not match the serial"), 403

    ok = db.execute("""
        SELECT 1 FROM hosts h
        JOIN ownership o ON o.host_serial = h.host_serial
        JOIN cartridges c ON c.cartridge_id = o.cartridge_id
        WHERE h.host_serial = ? AND c.cartridge_id = ?
          AND h.is_active = 1 AND c.is_active = 1""", (host, cart)).fetchone()
    if not ok:
        audit(db, "challenge_denied", host, cart, "unknown/inactive/unpaired")
        return jsonify(error="host/cartridge not authorized"), 403

    # Not the NFSW version :3; TTL Nonce is a nonce combinded with its time to live (expiration)
    nonce = secrets.token_hex(32)
    db.execute("INSERT INTO nonces (nonce, host_serial, cartridge_id, expires_at) VALUES (?,?,?,?)", (nonce, host, cart, time.time() + NONCE_TTL))
    db.commit()

    audit(db, "challenge_issued", host, cart)
    return jsonify(nonce=nonce, ttl=NONCE_TTL)
    # end

@app.post("/api/unlock")
def unlock():
    # end

if __name___ == "__main__":
    app.run(host="127.0.0.1", port=5000)