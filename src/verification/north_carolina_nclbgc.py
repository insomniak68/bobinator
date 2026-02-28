"""
North Carolina Licensing Board for General Contractors (NCLBGC) license scraper.

Endpoints:
  - Search: POST https://portal.nclbgc.org/Public/_Search/
    Form fields: AccountNumber, ClassificationDefinitionIdnt, QualifierAccountNumber,
                 CompanyName, FirstName, LastName, PhoneNumber, useSoundex,
                 streetAddress, PostalCode, City, StateCode
  - Detail: GET https://portal.nclbgc.org/Public/_ShowAccountDetails/?key=<encrypted_key>&Source=Search
  - Matters: GET https://portal.nclbgc.org/Public/_ShowNCLBGCPublicMatters/?key=<encrypted_key>

The search returns HTML with encrypted keys for each result. We must:
1. Search by license number to get the encrypted key
2. Fetch details using that key
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import Optional
from urllib.parse import unquote, quote
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://portal.nclbgc.org/Public"
SEARCH_URL = f"{BASE_URL}/_Search/"
DETAIL_URL = f"{BASE_URL}/_ShowAccountDetails/"
MATTERS_URL = f"{BASE_URL}/_ShowNCLBGCPublicMatters/"
TIMEOUT = 15

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Content-Type": "application/x-www-form-urlencoded",
}


def _parse_detail_html(html: str) -> dict:
    """Parse the account detail HTML fragment into structured fields."""
    soup = BeautifulSoup(html, "html.parser")
    fields = {}

    labels = soup.find_all("div", class_="display-label")
    for label in labels:
        key = label.get_text(strip=True)
        value_div = label.find_next_sibling("div", class_="display-field")
        if value_div:
            # For status, check for "License Not Valid" span
            not_valid_span = value_div.find("span")
            raw_text = value_div.get_text(" ", strip=True)
            fields[key] = raw_text

    # Parse classifications from the Active Classifications fieldset
    classifications = []
    for fieldset in soup.find_all("fieldset"):
        legend = fieldset.find("legend")
        if legend and "Classification" in legend.get_text():
            class_div = fieldset.find("div", class_="display-field")
            if class_div:
                # Classifications are separated by <br/>
                for text in class_div.stripped_strings:
                    classifications.append(text)

    fields["_classifications"] = classifications
    return fields


def _get_encrypted_key(license_number: str) -> Optional[str]:
    """Search for a license number and return the encrypted key for detail lookup."""
    # Strip the "L." prefix if present for the search
    num = license_number.lstrip("Ll.")

    try:
        resp = requests.post(
            SEARCH_URL,
            data={
                "AccountNumber": num,
                "ClassificationDefinitionIdnt": "",
                "QualifierAccountNumber": "",
                "CompanyName": "",
                "FirstName": "",
                "LastName": "",
                "PhoneNumber": "",
                "useSoundex": "false",
                "streetAddress": "",
                "PostalCode": "",
                "City": "",
                "StateCode": "",
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"NCLBGC search request failed: {e}")
        return None

    # Extract the encrypted key from ShowAccountDetails('...')
    match = re.search(r"ShowAccountDetails\(\s*'([^']+)'", resp.text)
    if match:
        return match.group(1)

    return None


def lookup_license(license_number: str) -> dict:
    """
    Look up a North Carolina NCLBGC license by number.
    Returns a dict with license details matching the same interface as the VA scraper.
    """
    key = _get_encrypted_key(license_number)
    if not key:
        return {"success": False, "license_number": license_number, "error": "License not found"}

    # Key comes URL-encoded from the page JS; use it directly in URL to avoid double-encoding
    detail_url = f"{DETAIL_URL}?key={key}&Source=Search"
    try:
        detail_resp = requests.get(
            detail_url,
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        detail_resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"NCLBGC detail request failed: {e}")
        return {"success": False, "license_number": license_number, "error": str(e)}

    fields = _parse_detail_html(detail_resp.text)

    # Parse status - NCLBGC shows "Active", "Archived", or empty
    raw_status = fields.get("Status", "").strip()
    if "License Not Valid" in raw_status:
        status = "INACTIVE"
    elif "Archived" in raw_status:
        status = "ARCHIVED"
    elif raw_status == "" or "Active" in raw_status:
        status = "ACTIVE"
    else:
        status = raw_status.upper()

    # Fetch matters (violations/disciplinary actions)
    violations = None
    try:
        matters_resp = requests.get(
            f"{MATTERS_URL}?key={key}",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        matters_resp.raise_for_status()
        matters_text = matters_resp.text.strip()
        if matters_text:
            violations = matters_text
    except requests.RequestException:
        pass

    classifications = fields.get("_classifications", [])

    return {
        "success": True,
        "license_number": fields.get("License #", license_number),
        "holder_name": fields.get("Name"),
        "license_class": fields.get("License Limitation"),
        "status": status,
        "expiration_date": fields.get("Expiration Date"),
        "initial_date": fields.get("First Issued Date"),
        "firm_type": fields.get("Account Type"),
        "specialties": ", ".join(classifications) if classifications else None,
        "address": fields.get("Address"),
        "violations": violations,
        "raw_html": detail_resp.text[:5000],
    }


def search_licenses(query: str, limit: int = 20) -> list[dict]:
    """
    Search NCLBGC by company name.
    Returns a list of basic license info dicts.
    """
    try:
        resp = requests.post(
            SEARCH_URL,
            data={
                "AccountNumber": "",
                "ClassificationDefinitionIdnt": "",
                "QualifierAccountNumber": "",
                "CompanyName": query,
                "FirstName": "",
                "LastName": "",
                "PhoneNumber": "",
                "useSoundex": "false",
                "streetAddress": "",
                "PostalCode": "",
                "City": "",
                "StateCode": "",
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"NCLBGC search failed: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for tr in soup.find_all("tr")[:limit]:
        cells = tr.find_all("td")
        if len(cells) >= 3:
            link = cells[0].find("a")
            lic_num = link.get_text(strip=True) if link else cells[0].get_text(strip=True)
            results.append({
                "license_number": lic_num,
                "name": cells[2].get_text(strip=True),
                "license_type": cells[1].get_text(strip=True),
                "board": "NCLBGC",
            })

    return results


if __name__ == "__main__":
    import json
    # Test with known NC licenses
    for lic in ["83060", "05812", "100177"]:
        print(f"\n=== License {lic} ===")
        result = lookup_license(lic)
        print(json.dumps(result, indent=2))
