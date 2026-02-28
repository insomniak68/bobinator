#!/usr/bin/env python3
"""Standalone cron script to re-verify all providers."""

import sys, os, json, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from src.database import init_db
from src.verification.engine import verify_all

init_db()
results = verify_all()
for r in results:
    status = "OK" if "results" in r else "ERROR"
    print(f"  [{status}] Provider {r['provider_id']} ({r['name']})")
    if "error" in r:
        print(f"    Error: {r['error']}")

print(f"\nVerified {len(results)} providers.")
