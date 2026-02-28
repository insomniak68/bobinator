"""Bobinator - Automated License/Insurance/Bond Verification Platform"""

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional
import os
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.database import get_db, init_db
from src.auth import hash_password, verify_password, create_session_token, get_provider_id_from_token
from src.verification.virginia_dpor import lookup_license as va_lookup
from src.verification.north_carolina_nclbgc import lookup_license as nc_lookup
from src.verification.engine import verify_provider, STATE_SCRAPERS

app = FastAPI(title="Bobinator", description="Automated contractor verification platform")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

STATES = {
    "VA": "Virginia",
    "NC": "North Carolina",
}

CITIES_BY_STATE = {
    "VA": [
        "Alexandria", "Arlington", "Charlottesville", "Chesapeake", "Danville",
        "Fairfax", "Fredericksburg", "Hampton", "Harrisonburg", "Lynchburg",
        "Manassas", "Newport News", "Norfolk", "Petersburg", "Portsmouth",
        "Reston", "Richmond", "Roanoke", "Suffolk", "Virginia Beach", "Williamsburg",
        "Winchester", "Woodbridge",
    ],
    "NC": [
        "Asheville", "Cary", "Chapel Hill", "Charlotte", "Durham",
        "Fayetteville", "Gastonia", "Greensboro", "Greenville", "Hickory",
        "High Point", "Jacksonville", "Raleigh", "Rocky Mount", "Wilmington",
        "Winston-Salem",
    ],
}

# Flat list for backward compat
ALL_CITIES = sorted(set(c for cities in CITIES_BY_STATE.values() for c in cities))

TRADES = ["painter", "roofer"]


def get_current_provider(request: Request):
    token = request.cookies.get("session")
    if not token:
        return None
    pid = get_provider_id_from_token(token)
    if not pid:
        return None
    db = get_db()
    try:
        return db.execute("SELECT * FROM providers WHERE id = ?", (pid,)).fetchone()
    finally:
        db.close()


@app.on_event("startup")
def startup():
    init_db()


# ---- Landing Page ----

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "provider": get_current_provider(request)})


# ---- Provider Registration ----

@app.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    return templates.TemplateResponse("register.html", {
        "request": request, "trades": TRADES, "cities_by_state": CITIES_BY_STATE,
        "states": STATES, "error": None,
        "provider": get_current_provider(request),
    })


@app.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    name: str = Form(...), business_name: str = Form(""), email: str = Form(...),
    phone: str = Form(""), trade: str = Form(...), city: str = Form(""),
    county: str = Form(""), state: str = Form("VA"), license_number: str = Form(""),
    password: str = Form(...),
):
    db = get_db()
    try:
        existing = db.execute("SELECT id FROM providers WHERE email = ?", (email,)).fetchone()
        if existing:
            return templates.TemplateResponse("register.html", {
                "request": request, "trades": TRADES, "cities_by_state": CITIES_BY_STATE,
                "states": STATES, "error": "Email already registered", "provider": None,
            })

        if state not in STATES:
            state = "VA"

        pw_hash = hash_password(password)
        cursor = db.execute("""
            INSERT INTO providers (name, business_name, email, phone, trade, city, county, state, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, business_name, email, phone, trade, city, county, state, pw_hash))
        provider_id = cursor.lastrowid

        if license_number:
            db.execute("""
                INSERT INTO licenses (provider_id, license_number, state)
                VALUES (?, ?, ?)
            """, (provider_id, license_number, state))

        db.commit()

        token = create_session_token(provider_id)
        response = RedirectResponse("/dashboard", status_code=303)
        response.set_cookie("session", token, httponly=True, max_age=86400 * 30)
        return response
    finally:
        db.close()


# ---- Login/Logout ----

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "provider": None})


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    db = get_db()
    try:
        provider = db.execute("SELECT * FROM providers WHERE email = ?", (email,)).fetchone()
        if not provider or not verify_password(password, provider["password_hash"]):
            return templates.TemplateResponse("login.html", {
                "request": request, "error": "Invalid email or password", "provider": None,
            })
        token = create_session_token(provider["id"])
        response = RedirectResponse("/dashboard", status_code=303)
        response.set_cookie("session", token, httponly=True, max_age=86400 * 30)
        return response
    finally:
        db.close()


@app.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("session")
    return response


# ---- Provider Dashboard ----

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    provider = get_current_provider(request)
    if not provider:
        return RedirectResponse("/login", status_code=303)

    db = get_db()
    try:
        license_ = db.execute("SELECT * FROM licenses WHERE provider_id = ?", (provider["id"],)).fetchone()
        insurance = db.execute("SELECT * FROM insurance_records WHERE provider_id = ?", (provider["id"],)).fetchone()
        bond = db.execute("SELECT * FROM bond_records WHERE provider_id = ?", (provider["id"],)).fetchone()
        logs = db.execute(
            "SELECT * FROM verification_log WHERE provider_id = ? ORDER BY checked_at DESC LIMIT 20",
            (provider["id"],)
        ).fetchall()
        return templates.TemplateResponse("dashboard.html", {
            "request": request, "provider": provider, "license": license_,
            "insurance": insurance, "bond": bond, "logs": logs,
        })
    finally:
        db.close()


@app.post("/dashboard/verify", response_class=HTMLResponse)
async def trigger_verify(request: Request):
    provider = get_current_provider(request)
    if not provider:
        return RedirectResponse("/login", status_code=303)
    verify_provider(provider["id"])
    return RedirectResponse("/dashboard", status_code=303)


# ---- Public Directory ----

@app.get("/directory", response_class=HTMLResponse)
async def directory(request: Request, trade: str = "", city: str = "", state: str = "", verified: str = ""):
    db = get_db()
    try:
        query = """
            SELECT p.*, l.status as license_status, l.license_class, l.license_number, l.expiration_date as lic_expiry
            FROM providers p
            LEFT JOIN licenses l ON l.provider_id = p.id
            WHERE 1=1
        """
        params = []
        if trade:
            query += " AND p.trade = ?"
            params.append(trade)
        if city:
            query += " AND p.city = ?"
            params.append(city)
        if state:
            query += " AND p.state = ?"
            params.append(state)
        if verified == "yes":
            query += " AND l.status = 'ACTIVE'"
        elif verified == "no":
            query += " AND (l.status IS NULL OR l.status != 'ACTIVE')"

        query += " ORDER BY p.name"
        providers = db.execute(query, params).fetchall()
        return templates.TemplateResponse("directory.html", {
            "request": request, "providers": providers, "trades": TRADES,
            "cities": ALL_CITIES, "states": STATES, "trade": trade, "city": city,
            "state": state, "verified": verified,
            "provider": get_current_provider(request),
        })
    finally:
        db.close()


# ---- Provider Profile (public) ----

@app.get("/provider/{provider_id}", response_class=HTMLResponse)
async def provider_profile(request: Request, provider_id: int):
    db = get_db()
    try:
        p = db.execute("SELECT * FROM providers WHERE id = ?", (provider_id,)).fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Provider not found")
        license_ = db.execute("SELECT * FROM licenses WHERE provider_id = ?", (provider_id,)).fetchone()
        insurance = db.execute("SELECT * FROM insurance_records WHERE provider_id = ?", (provider_id,)).fetchone()
        bond = db.execute("SELECT * FROM bond_records WHERE provider_id = ?", (provider_id,)).fetchone()
        return templates.TemplateResponse("provider_profile.html", {
            "request": request, "p": p, "license": license_,
            "insurance": insurance, "bond": bond,
            "provider": get_current_provider(request),
        })
    finally:
        db.close()


# ---- Admin ----

@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    db = get_db()
    try:
        providers = db.execute("""
            SELECT p.*, l.status as license_status, l.license_number
            FROM providers p LEFT JOIN licenses l ON l.provider_id = p.id
            ORDER BY p.created_at DESC
        """).fetchall()
        logs = db.execute("""
            SELECT vl.*, p.name as provider_name
            FROM verification_log vl JOIN providers p ON p.id = vl.provider_id
            ORDER BY vl.checked_at DESC LIMIT 50
        """).fetchall()
        return templates.TemplateResponse("admin.html", {
            "request": request, "providers": providers, "logs": logs,
            "provider": get_current_provider(request),
        })
    finally:
        db.close()


# ---- API Endpoints ----

@app.get("/api/license/lookup/{state}/{license_number}")
async def api_license_lookup(state: str, license_number: str):
    state = state.upper()
    scraper = STATE_SCRAPERS.get(state)
    if not scraper:
        return {"success": False, "error": f"Unsupported state: {state}"}
    return scraper(license_number)


# Keep old endpoint for backward compat
@app.get("/api/dpor/lookup/{license_number}")
async def api_dpor_lookup(license_number: str):
    return va_lookup(license_number)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
