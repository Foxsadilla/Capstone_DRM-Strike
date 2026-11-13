# Name: provision.py
# Nodes: server (/root/validator/)
# Purpose: Registers the cartidge and prints a new key to stdout
# Last Updated: 11/07/2026
# ==============================================

import secrets, sys
from db import connect, init_db

cart_id, host_serial, owner_id = sys.argv[1:4]
key = secrets.token_hex(32)

init_db()
db = connect()
db.execute("INSERT INTO cartridges (cartridge_id, luks_key) VALUES (?, ?)", (cart_id, key))
db.execute("INSERT OR IGNORE INTO hosts (host_serial, owner_id) VALUES (?, ?)", (host_serial, owner_id))
db.execute("INSERT OR IGNORE INTO ownership VALUES (?, ?)", (host_serial, cart_id))
db.commit()

# This prevents there being no new line and instead the ecact bytes become the LUKS passphrase!
sys.stdout.write(key)