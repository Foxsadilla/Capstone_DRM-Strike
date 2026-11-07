# Name: server-db.py
# Nodes: server (/root/validator/)
# Purpose: Create the SQL database for the server for managing client devices
# Last Updated: 11/07/2026
# ==============================================

import sqlite3

DB_PATH = "/root/validator/server_database.db"

def connect():
    # DO NOT USE "connect", it'll cause conflicts.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
    # end

def init_db():
    conn = connect()
    # In the cartridge section, luks key is escrowed!
    conn.executescript("""
    CREATE TABLE IF NOT EXSITS hosts (
        host_serial TEXT PRIMARY KEY,
        owner_id    TEXT NOT NULL,
        is_active   INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS cartridges (
        cartridge_id TEXT PRIMARY KEY,
        luks_key     TEXT NOT NULL,
        is_active    INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS ownership (
        host_serial TEXT NOT NULL REFERENCES hosts(host_serial),
        cartridge_id TEXT NOT NULL REFERENCES cartridges(cartridge_id),
        PRIMARY KEY (host_serial, cartridge_id)
    );
    CREATE TABLE IF NOT EXISTS nonces (
        nonce        TEXT PRIMARY KEY,
        host_serial  TEXT NOT NULL,
        cartridge_id TEXT NOT NULL,
        expires_at   REAL NOT NULL,
        used         INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS audit (
        ts REAL, event TEXT, host_serial TEXT, cartridge_id TEXT, detail TEXT
    );

    """)
    conn.commit()
    conn.close()
    # end
