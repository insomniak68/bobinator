# Bobinator 🔍

Automated license, insurance, and bond verification platform for Virginia service providers.

## What It Does

- **Consumers**: Search a directory of contractors, see verified license/insurance/bond status
- **Providers**: Register, enter credentials, get automatically verified against Virginia DPOR
- **Admin**: View all providers, verification logs, failed checks

## Tech Stack

- **Backend**: FastAPI + SQLite
- **Frontend**: Jinja2 + Tailwind CSS (CDN)
- **Verification**: Scrapes Virginia DPOR License Lookup (Board for Contractors)
- **Deployment**: k3s cluster with MetalLB VIP (10.20.30.44)

## Quick Start

```bash
pip install -r requirements.txt
python scripts/seed_test_data.py
uvicorn src.main:app --reload
```

Visit http://localhost:8000

## DPOR Scraper

The scraper queries `https://dporweb.dpor.virginia.gov/LicenseLookup/` — a simple POST form. No API key needed. Returns license status, class, expiration, holder name, specialties, etc.

## Cron Verification

```bash
python scripts/verify_all.py
```

## Deployment

```bash
docker build -t bobinator .
kubectl apply -f k8s/
```

## Trades Covered

- ✅ Painters (Phase 1)
- ✅ Roofers (Phase 1)
- 🔜 Plumbers, Carpenters, General Contractors (Phase 2)
