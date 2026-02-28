"""
Virginia DPOR (Department of Professional and Occupational Regulation) license scraper.

Endpoints:
  - Search: POST https://dporweb.dpor.virginia.gov/LicenseLookup/Search
    Form fields: search-text, phone-number (honeypot, leave empty)
  - Detail: POST https://dporweb.dpor.virginia.gov/LicenseLookup/LicenseDetail
    Form fields: license-number, phone-number (honeypot, leave empty)
"""

import requests
from bs4 import BeautifulSoup
from typing import Optional
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://dporweb.dpor.virginia.gov/LicenseLookup"
SEARCH_URL = f"{BASE_URL}/Search"
DETAIL_URL = f"{BASE_URL}/LicenseDetail"
TIMEOUT = 15

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Content-Type": "application/x-www-form-urlencoded",
}


def lookup_license(license_number: str) -> dict:
    """
    Look up a Virginia DPOR license by number.
    Returns a dict with license details or error info.
    """
    try:
        resp = requests.post(
            DETAIL_URL,
            data={"license-number": license_number, "phone-number": ""},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"DPOR request failed: {e}")
        return {"success": False, "license_number": license_number, "error": str(e)}

    soup = BeautifulSoup(resp.text, "html.parser")

    # Check if we got a detail page or an error
    detail_tab = soup.find("div", id="license-details-tab")
    if not detail_tab:
        # Maybe the license doesn't exist - check for alert
        alert = soup.find("div", class_="alert-danger")
        error_msg = alert.get_text(strip=True) if alert else "License not found or invalid response"
        return {"success": False, "license_number": license_number, "error": error_msg}

    # Parse key-value pairs from the detail page
    fields = {}
    labels = detail_tab.find_all("strong")
    for label in labels:
        key = label.get_text(strip=True)
        # The value is in the next col-xs-6 sibling
        parent_div = label.find_parent("div")
        if parent_div:
            value_div = parent_div.find_next_sibling("div")
            if value_div:
                fields[key] = value_div.get_text(strip=True)

    # If no Status field is present, the license is active
    status = fields.get("Status", "ACTIVE")

    return {
        "success": True,
        "license_number": license_number,
        "holder_name": fields.get("Name"),
        "license_class": fields.get("Rank"),
        "status": status,
        "expiration_date": fields.get("Expiration Date"),
        "initial_date": fields.get("Initial Certification Date"),
        "firm_type": fields.get("Firm Type"),
        "specialties": fields.get("Specialties"),
        "address": fields.get("Address"),
        "raw_html": resp.text[:5000],
    }


def search_licenses(query: str, limit: int = 20) -> list[dict]:
    """
    Search DPOR by name, business name, or license number.
    Returns a list of basic license info dicts.
    """
    try:
        resp = requests.post(
            SEARCH_URL,
            data={"search-text": query, "phone-number": ""},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"DPOR search failed: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", id="search-results")
    if not table:
        return []

    results = []
    rows = table.find("tbody")
    if not rows:
        rows = table
    for tr in rows.find_all("tr")[:limit]:
        cells = tr.find_all("td")
        if len(cells) >= 5:
            license_input = cells[0].find("input", {"name": "license-number"})
            lic_num = license_input["value"] if license_input else cells[0].get_text(strip=True)
            results.append({
                "license_number": lic_num,
                "name": cells[1].get_text(strip=True),
                "address": cells[2].get_text(strip=True),
                "license_type": cells[3].get_text(strip=True),
                "board": cells[4].get_text(strip=True),
            })
    return results


if __name__ == "__main__":
    import json
    # Test with a known license
    result = lookup_license("2705081693")
    print(json.dumps(result, indent=2))
