# Name: server.py
# Nodes: server (/root/validator/)
# Purpose: Simulates the function of ther server
# Last Updated: 11/10/2026
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

app = Flask(__name__)
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
    db = connect()

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
    cn = verified_cn()
    body = request.get_json(force=True)
    nonce = body.get("nonce", "")
    try:
        signature = bytes.fromhex(body.get("signature",""))
    except ValueError:
        return jsonify(error="Bad signature encoding"), 400

    db = connect()
    row = db.execute("SELECT host_serial, cartridge_id FROM nonces WHERE nonce = ?", (nonce,)).fetchone()

    if not row or row["host_serial"] != cn:
        return jsonify(error="invalid nonce"), 400

    host, cart = row["host_serial"], row["cartridge_id"]

    # Cheddar and BBQ Wavy and Sour Cream and Onion Equals a 3 Layer Dip Stack (aka atomic single use value):
    cur = db.execute("UPDATE nonces SET used = 1 WHERE nonce = ? AND used = 0 AND expires_at > ?", (nonce, time.time()))

    db.commit()
    if cur.rowcount != 1:
        audit(db, "replay_or_expired", host, cart, nonce[:8])
        return jsonify(error="nonce has expired or has been already used"), 403
    
    # Verify the signature fo the cartridhe bu sing ots certifcate's pub key
    try:
        with open(os.path.join(ISSUED_DIR, f"{cart}.crt"), "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        pub = cert.public_key()
        pub.verify(signature, bytes.fromhex(nonce), padding.PKCS1v15(), hashes.SHA256())
    except (InvalidSignature, FileNotFoundError):
        audit(db, "cartridge_auth_failed", host, cart)
        return jsonify(error="Cartridhes authentication has failed"), 403

    # Handle the key for the encrypted image on the cartridge. Only the real one can unwrap
    luks_key = db.execute("SELECT luks_key FROM cartridges WHERE cartridge_id = ?", (cart,)).fetchone()[0]
    wrapped = pub.encrypt(luks_key.encode(), OAEP)
    audit(db, "key_released", host, cart)
    return jsonify(wrapped_key=wrapped.hex())
    # end

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)