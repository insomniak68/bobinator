"""
Verification engine - orchestrates credential verification for providers.
"""

import logging
from datetime import datetime
from .virginia_dpor import lookup_license
from ..database import get_db

logger = logging.getLogger(__name__)


def verify_license(provider_id: int) -> dict:
    """Verify a provider's DPOR license and update the database."""
    db = get_db()
    try:
        lic = db.execute("SELECT * FROM licenses WHERE provider_id = ?", (provider_id,)).fetchone()
        if not lic:
            return {"success": False, "error": "No license on file"}

        result = lookup_license(lic["license_number"])
        now = datetime.utcnow().isoformat()

        if result["success"]:
            db.execute("""
                UPDATE licenses SET
                    status = ?, license_class = ?, expiration_date = ?,
                    holder_name = ?, firm_type = ?, specialties = ?,
                    address = ?, last_verified_at = ?, raw_response = ?
                WHERE id = ?
            """, (
                result.get("status"), result.get("license_class"),
                result.get("expiration_date"), result.get("holder_name"),
                result.get("firm_type"), result.get("specialties"),
                result.get("address"), now, result.get("raw_html"),
                lic["id"],
            ))

        # Log the verification attempt
        db.execute("""
            INSERT INTO verification_log (provider_id, credential_type, result, details, checked_at)
            VALUES (?, 'license', ?, ?, ?)
        """, (
            provider_id,
            "verified" if result["success"] else "failed",
            str(result.get("status") or result.get("error", "")),
            now,
        ))
        db.commit()
        return result
    finally:
        db.close()


def check_insurance_expiry(provider_id: int) -> dict:
    """Check if insurance is expired."""
    db = get_db()
    try:
        rec = db.execute("SELECT * FROM insurance_records WHERE provider_id = ?", (provider_id,)).fetchone()
        if not rec:
            return {"success": False, "error": "No insurance on file"}

        now = datetime.utcnow().strftime("%Y-%m-%d")
        expired = rec["expiration_date"] and rec["expiration_date"] < now
        result_str = "expired" if expired else "valid"

        db.execute("""
            INSERT INTO verification_log (provider_id, credential_type, result, details)
            VALUES (?, 'insurance', ?, ?)
        """, (provider_id, result_str, f"Expires: {rec['expiration_date']}"))
        db.commit()
        return {"success": True, "status": result_str, "expiration_date": rec["expiration_date"]}
    finally:
        db.close()


def check_bond_expiry(provider_id: int) -> dict:
    """Check if bond is expired."""
    db = get_db()
    try:
        rec = db.execute("SELECT * FROM bond_records WHERE provider_id = ?", (provider_id,)).fetchone()
        if not rec:
            return {"success": False, "error": "No bond on file"}

        now = datetime.utcnow().strftime("%Y-%m-%d")
        expired = rec["expiration_date"] and rec["expiration_date"] < now
        result_str = "expired" if expired else "valid"

        db.execute("""
            INSERT INTO verification_log (provider_id, credential_type, result, details)
            VALUES (?, 'bond', ?, ?)
        """, (provider_id, result_str, f"Expires: {rec['expiration_date']}"))
        db.commit()
        return {"success": True, "status": result_str, "expiration_date": rec["expiration_date"]}
    finally:
        db.close()


def verify_provider(provider_id: int) -> dict:
    """Run all verifications for a provider."""
    results = {
        "license": verify_license(provider_id),
        "insurance": check_insurance_expiry(provider_id),
        "bond": check_bond_expiry(provider_id),
    }
    return results


def verify_all():
    """Re-verify all active providers. Designed to be called from cron."""
    db = get_db()
    try:
        providers = db.execute("SELECT id, name FROM providers").fetchall()
        results = []
        for p in providers:
            logger.info(f"Verifying provider {p['id']}: {p['name']}")
            try:
                r = verify_provider(p["id"])
                results.append({"provider_id": p["id"], "name": p["name"], "results": r})
            except Exception as e:
                logger.error(f"Error verifying provider {p['id']}: {e}")
                results.append({"provider_id": p["id"], "name": p["name"], "error": str(e)})
        return results
    finally:
        db.close()
