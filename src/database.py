import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get("BOBINATOR_DB", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bobinator.db"))


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS providers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        business_name TEXT,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        trade TEXT NOT NULL,
        city TEXT,
        county TEXT,
        state TEXT DEFAULT 'VA',
        password_hash TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_id INTEGER NOT NULL REFERENCES providers(id),
        license_number TEXT NOT NULL,
        state TEXT DEFAULT 'VA',
        license_class TEXT,
        status TEXT,
        expiration_date TEXT,
        holder_name TEXT,
        initial_date TEXT,
        firm_type TEXT,
        specialties TEXT,
        address TEXT,
        last_verified_at TEXT,
        raw_response TEXT,
        UNIQUE(provider_id, license_number)
    );

    CREATE TABLE IF NOT EXISTS insurance_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_id INTEGER NOT NULL REFERENCES providers(id),
        carrier TEXT,
        policy_number TEXT,
        coverage_amount REAL,
        expiration_date TEXT,
        proof_uploaded INTEGER DEFAULT 0,
        verified INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS bond_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_id INTEGER NOT NULL REFERENCES providers(id),
        bond_company TEXT,
        bond_number TEXT,
        amount REAL,
        expiration_date TEXT,
        proof_uploaded INTEGER DEFAULT 0,
        verified INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS verification_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_id INTEGER NOT NULL REFERENCES providers(id),
        credential_type TEXT NOT NULL,
        result TEXT NOT NULL,
        details TEXT,
        checked_at TEXT DEFAULT (datetime('now'))
    );
    """)
    conn.commit()
    conn.close()
