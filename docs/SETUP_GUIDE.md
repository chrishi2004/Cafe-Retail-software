# Setup Guide

## Purpose

This guide explains how to run the full-stack project locally with a local PostgreSQL database.

Use it when setting up the project for development, demo recording, interview walkthroughs, or QA.

## Prerequisites

Install:

- Python 3.11 or newer
- Node.js 18 or newer
- PostgreSQL 14 or newer
- PowerShell
- Git

Optional:

- Power BI Desktop
- PostgreSQL command-line tools: `pg_dump`, `pg_restore`, `psql`
- Cloudflare Tunnel, Tailscale, or ngrok for remote access demos

## Repository Layout

```text
backend/    FastAPI backend, SQLAlchemy models, Alembic migrations, tests, seed script
frontend/   React TypeScript dashboard
docs/       Project documentation and portfolio packaging
powerbi/    Power BI screenshots and placeholders
scripts/    Local PostgreSQL backup and restore helpers
```

## Environment Files

Root `.env.example` documents backend settings:

```text
APP_NAME="Hybrid Retail BI API"
ENVIRONMENT=development
API_PREFIX=/api
FRONTEND_ORIGIN=http://localhost:5173
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/hybrid_retail_bi
SECRET_KEY=change-me-in-development
ACCESS_TOKEN_EXPIRE_MINUTES=60
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
```

Frontend `.env.example`:

```text
VITE_API_BASE_URL=http://localhost:8000/api
```

Rules:

- Copy examples into local `.env` files.
- Do not commit real `.env` files.
- Replace `SECRET_KEY` before any remote demo.
- Keep PostgreSQL local/private for the default architecture.

## 1. Create Local PostgreSQL Database

Create the development database in PostgreSQL:

```powershell
createdb hybrid_retail_bi
```

If `createdb` is not in PATH, use pgAdmin or the PostgreSQL shell to create a database named:

```text
hybrid_retail_bi
```

The default connection string is:

```text
postgresql+psycopg://postgres:postgres@localhost:5432/hybrid_retail_bi
```

Adjust username, password, host, or port in `backend/.env` if your local PostgreSQL setup differs.

## 2. Backend Setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\.env.example .env
```

Run migrations:

```powershell
alembic upgrade head
```

Seed demo data:

```powershell
python -m scripts.seed --reset
```

The seed script also creates the Version 2 billing foundation:

- Demo company: `Hybrid Retail Demo Private Limited`
- Trade name: `Hybrid Retail Demo`
- PAN: `ABCDE1234F`
- Primary GSTIN: `29ABCDE1234F1Z5`
- Branch GST/state records for Bengaluru, Delhi, and Pune demo branches
- GST rates: `0%`, `5%`, `12%`, `18%`, and `28%`
- Payment modes: Cash, UPI, Card, Bank Transfer, and Credit
- Default GST invoice sequence: `INV-2026-00001`

GST, e-invoice, and e-way bill features in this project are portfolio/demo operational aids. Have all tax setup, reports, and filing data reviewed by a qualified CA/GST expert before using them for a real business.

Start the API:

```powershell
uvicorn app.main:app --reload
```

Health check:

```text
http://localhost:8000/api/health
```

## 3. Frontend Setup

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

Open:

```text
http://localhost:5173
```

## 4. Demo Login

Seeded users use:

```text
RetailDemo@123
```

Common accounts:

| Role | Email |
| --- | --- |
| Admin | `admin@hybridretail.test` |
| Store Manager | `manager.central@hybridretail.test` |
| Staff | `staff.north@hybridretail.test` |
| Analyst | `analyst@hybridretail.test` |

See [Demo Credentials](DEMO_CREDENTIALS.md) for all seeded accounts.

## 5. Run Tests

Backend workflow regression:

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m pytest tests/test_business_workflows.py -q
```

Backend grouped regression:

```powershell
python -m pytest tests/test_auth.py tests/test_master_data.py tests/test_inventory.py tests/test_sales.py -q
python -m pytest tests/test_reorder.py tests/test_purchase_orders.py tests/test_dashboard.py tests/test_forecasts.py -q
python -m pytest tests/test_ai.py tests/test_exports.py tests/test_business_workflows.py -q
```

Frontend checks:

```powershell
cd frontend
npm run typecheck
npm run build
```

## 6. Power BI Setup

Power BI Desktop can use either:

- Local PostgreSQL reporting views.
- Authenticated CSV exports from the web app/API.

Read [Power BI Setup](POWER_BI_SETUP.md).

## 7. Remote Access Setup

Run the app locally first, then expose only the dashboard/API through one of:

- Cloudflare Tunnel
- Tailscale
- ngrok

Read [Remote Access](REMOTE_ACCESS.md).

Important: do not expose PostgreSQL port `5432`.

## 8. Backup And Restore

Manual backup and helper scripts are documented in [Backup And Restore](BACKUP_RESTORE.md).

Example helper:

```powershell
.\scripts\backup_postgres.ps1
```

## 9. Common Troubleshooting

### Backend cannot connect to database

Check:

- PostgreSQL service is running.
- Database name exists.
- `DATABASE_URL` in `backend/.env` matches your local credentials.
- Migrations were run with `alembic upgrade head`.

### Frontend cannot call API

Check:

- Backend is running on `http://localhost:8000`.
- Frontend `.env` has `VITE_API_BASE_URL=http://localhost:8000/api`.
- Backend `FRONTEND_ORIGIN` matches `http://localhost:5173`.

### Login fails after seed

Check:

- You ran `python -m scripts.seed --reset`.
- You are using the seeded email exactly.
- The password is `RetailDemo@123`.

### Power BI views are missing

Run:

```powershell
cd backend
.venv\Scripts\Activate.ps1
alembic upgrade head
```

### Backup scripts cannot find PostgreSQL tools

Install PostgreSQL client tools or add their `bin` folder to PATH.

## Related Docs

- [Architecture](ARCHITECTURE.md)
- [Case Study](CASE_STUDY.md)
- [Demo Script](DEMO_SCRIPT.md)
- [QA Checklist](QA_CHECKLIST.md)
- [Power BI Setup](POWER_BI_SETUP.md)
- [Remote Access](REMOTE_ACCESS.md)
- [Backup And Restore](BACKUP_RESTORE.md)
- [Screenshots Guide](SCREENSHOTS.md)
