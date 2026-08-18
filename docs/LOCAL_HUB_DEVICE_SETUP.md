# Portable Local Hub Device Setup

This is the low-cost operating profile for the project. The current Windows
device runs PostgreSQL and the full Local Hub API. The repository remains
portable: another device can repeat this setup without copying secrets or
machine-specific data.

## Architecture

- Vercel frontend: public static frontend hosting.
- Vercel cloud gateway: HC2-HC4 coordination routes only.
- Local Hub on the owner device: authentication, Retail, Cafe, billing,
  dashboards, exports, AI, governance, and the operational database.
- Optional Cloudflare Tunnel or Tailscale: remote access to the Local Hub.
- PostgreSQL: local only; never expose port 5432 publicly.

## First-device setup

1. Install PostgreSQL and create a local cluster.
2. Add PostgreSQL's `bin` directory to the user's PATH so `psql`,
   `pg_isready`, `pg_dump`, and `pg_restore` work in a new terminal.
3. Create the `hybrid_retail_bi` database and a least-privilege application
   user. Keep the password only in `backend/.env`.
4. From `backend`, install `requirements.txt` into `.venv`.
5. Copy the repository root `.env.example` to `backend/.env` and set
   `DEPLOYMENT_MODE=local_hub`, a strong `SECRET_KEY`, and the local database
   URL. Never commit this file.
6. Apply migrations:

   ```powershell
   cd backend
   .venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
   ```

7. Seed the ownership-aware demo data:

   ```powershell
   .venv\Scripts\python.exe scripts\seed_multi_venture.py --reset
   ```

8. Start the portable local profile:

   ```powershell
   ..\scripts\start_local_hub.ps1
   ```

9. Verify it:

   ```powershell
   ..\scripts\check_local_hub.ps1
   ```

## Moving to another device

Copy only the repository. Do not copy `backend/.env`, `.venv`, database data
folders, backups, or tokens. Repeat the first-device setup, then restore a
backup if existing business data is required.

## Remote access

For private access, use Tailscale Serve. For a public demo, use a named
Cloudflare Tunnel and expose the API/frontend entrypoint—not PostgreSQL. Set
`FRONTEND_ORIGIN` to the actual dashboard origin and update the Vercel
frontend's `VITE_API_BASE_URL` to the Local Hub HTTPS URL.

Before public use, complete MFA/TOTP, browser E2E, backup/restore, trusted
proxy, edge rate-limit, and dependency-audit gates from the P11 release report.
