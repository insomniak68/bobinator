#!/usr/bin/env python3
"""Seed test data into Bobinator database."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.database import get_db, init_db
from src.auth import hash_password

init_db()
db = get_db()

pw = hash_password("test123")

providers = [
    # Real VA license numbers found from DPOR
    ("John Smith", "K & A Roofing Inc", "john@karoofing.com", "804-555-0101", "roofer", "Richmond", "Henrico", "VA", "2705081693"),
    ("Mike Johnson", "Colbert Roofing Corp", "mike@colbertroofing.com", "703-555-0102", "roofer", "Newport News", "Newport News", "VA", "2701013163"),
    ("Sarah Davis", "McNabb Roofing Co", "sarah@mcnabbroofing.com", "703-555-0103", "roofer", "Haymarket", "Prince William", "VA", "2705014734"),
    # Fake VA providers for testing
    ("Bob Painter", "Bob's Quality Painting LLC", "bob@bobpainting.com", "804-555-0201", "painter", "Richmond", "Richmond", "VA", "2705999999"),
    ("Alice Roofer", "Top Notch Roofing", "alice@topnotch.com", "757-555-0301", "roofer", "Virginia Beach", "Virginia Beach", "VA", ""),
    ("Carlos Martinez", "Martinez Painting Services", "carlos@martinezpaint.com", "571-555-0401", "painter", "Fairfax", "Fairfax", "VA", ""),
    # Real NC license numbers from NCLBGC
    ("Baker Roofing", "Baker Roofing Company, LLC", "info@bakerroofing.com", "919-828-2975", "roofer", "Cary", "Wake", "NC", "05812"),
    ("Honour Roofing", "Honour Roofing and Construction, LLC", "info@honourroofing.com", "919-621-0300", "roofer", "Raleigh", "Wake", "NC", "100177"),
    ("Mac Brother", "Mac Brother Painting and Construction LLC", "info@macbrother.com", "910-670-5707", "painter", "Fayetteville", "Cumberland", "NC", "101450"),
]

for name, biz, email, phone, trade, city, county, state, lic in providers:
    existing = db.execute("SELECT id FROM providers WHERE email = ?", (email,)).fetchone()
    if existing:
        print(f"  Skipping {email} (exists)")
        continue

    cursor = db.execute("""
        INSERT INTO providers (name, business_name, email, phone, trade, city, county, state, password_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, biz, email, phone, trade, city, county, state, pw))
    pid = cursor.lastrowid
    print(f"  Created provider {pid}: {name} ({biz}) [{state}]")

    if lic:
        db.execute("INSERT INTO licenses (provider_id, license_number, state) VALUES (?, ?, ?)", (pid, lic, state))
        print(f"    License: {lic} ({state})")

# Add some insurance/bond records for first provider
first = db.execute("SELECT id FROM providers LIMIT 1").fetchone()
if first:
    pid = first["id"]
    if not db.execute("SELECT id FROM insurance_records WHERE provider_id = ?", (pid,)).fetchone():
        db.execute("""
            INSERT INTO insurance_records (provider_id, carrier, policy_number, coverage_amount, expiration_date, proof_uploaded, verified)
            VALUES (?, 'State Farm', 'INS-2026-001', 1000000, '2027-01-15', 1, 1)
        """, (pid,))
    if not db.execute("SELECT id FROM bond_records WHERE provider_id = ?", (pid,)).fetchone():
        db.execute("""
            INSERT INTO bond_records (provider_id, bond_company, bond_number, amount, expiration_date, proof_uploaded, verified)
            VALUES (?, 'Travelers', 'BND-2026-001', 50000, '2027-03-01', 1, 1)
        """, (pid,))

db.commit()
db.close()
print("Done seeding!")
