# Remote Access And Hybrid Local-First Deployment

This guide explains how to access the Hybrid Retail BI dashboard remotely while keeping the main business database local.

The remote access goal is simple:

- Admins open the web dashboard from outside the store.
- The browser talks to the frontend and backend API only.
- PostgreSQL stays on the local machine or private LAN.
- The database port is never exposed publicly.
- Every remote user still has to log in through the application.

## Local-First Architecture

```mermaid
flowchart LR
    Admin["Remote admin browser"] --> Access["Cloudflare Tunnel, Tailscale, or ngrok"]
    Access --> Frontend["Frontend dashboard"]
    Frontend --> API["FastAPI backend"]
    API --> Auth["App auth and RBAC"]
    API --> DB[("Local PostgreSQL")]
    Staff["Store staff on local network"] --> Frontend
    PowerBI["Power BI Desktop"] --> DB

    classDef private fill:#eef7f2,stroke:#2f8f63,color:#173b29;
    classDef public fill:#edf4ff,stroke:#276fbf,color:#17324a;
    class DB,API,Auth private;
    class Admin,Access public;
```

Remote traffic should terminate at the dashboard/API layer. The backend then decides what data the user can see based on authentication, role, and branch scope.

## Why The Database Remains Local

Keeping the database local supports the main project promise: remote visibility without the cost and operational overhead of a paid cloud database.

Benefits:

- Lower recurring infrastructure cost for a small retail business.
- Data remains close to the store where sales and stock updates happen.
- Existing Power BI Desktop and local backup workflows can connect directly on the trusted machine.
- Remote exposure can be limited to the authenticated application instead of the full database.

Do not publish PostgreSQL on the internet. In the default project setup, PostgreSQL should listen only on localhost or a private LAN interface. Remote users should never connect directly to port `5432`.

## Local Run Baseline

Run the backend and frontend locally first.

Backend:

```powershell
cd backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

For a cleaner deployment later, serve a production frontend build through a reverse proxy or through the backend host, then expose one HTTP entrypoint instead of two development ports.

## Recommended Option For Portfolio Demo

Use **Cloudflare Tunnel** for a polished public demo URL.

Why:

- It can expose a local HTTP service through outbound-only `cloudflared` connections.
- It does not require opening inbound firewall ports.
- It gives a clean public hostname when configured with a Cloudflare-managed domain.
- It works well for showing the project to interviewers or reviewers.

Use **Tailscale** when the dashboard should be private to trusted devices only. Use **ngrok** when you need a short-lived demo quickly.

## Option A: Cloudflare Tunnel

Best for: public demo URL or a small business admin dashboard with a managed hostname.

High-level setup:

1. Create or use a Cloudflare account.
2. Add a domain to Cloudflare if you want a stable hostname such as `retail-demo.example.com`.
3. Install `cloudflared` on the local machine that runs the dashboard.
4. Create a tunnel from the Cloudflare dashboard or CLI.
5. Map a public hostname to the local dashboard service.
6. Run the tunnel connector on the local machine.
7. Open the public URL and confirm the app login page appears.
8. Confirm API calls work through the same public route or configured API route.
9. Confirm PostgreSQL is not reachable from the public internet.

Quick development tunnel:

```powershell
cloudflared tunnel --url http://localhost:5173
```

This creates a random `trycloudflare.com` URL for testing. For a portfolio demo, create a named tunnel and stable hostname.

Production-style notes:

- Prefer exposing one reverse-proxied app URL instead of exposing separate frontend and API URLs.
- Add Cloudflare Access in front of the app if you want an extra identity gate before the app login.
- Keep the app's own login enabled even when Cloudflare Access is used.
- Run `cloudflared` as a service for a stable demo machine.

Official reference: [Cloudflare Tunnel docs](https://developers.cloudflare.com/tunnel/) and [Cloudflare Tunnel setup](https://developers.cloudflare.com/tunnel/setup/)

## Option B: Tailscale

Best for: private admin access from trusted laptops and phones.

High-level setup:

1. Create a Tailscale account and tailnet.
2. Install Tailscale on the local machine that runs the dashboard.
3. Install Tailscale on the admin device.
4. Sign in on both devices.
5. Keep MagicDNS enabled so devices have stable tailnet names.
6. Start the backend and frontend locally.
7. Use Tailscale Serve to expose the dashboard to the tailnet.
8. Open the Serve URL from another signed-in tailnet device.
9. Confirm the dashboard requires application login.
10. Use Tailscale ACLs if only specific users/devices should access the dashboard host.

Example for a local frontend on port `5173`:

```powershell
tailscale serve 5173
```

Example for a production app entrypoint on port `8080`:

```powershell
tailscale serve 8080
```

Tailscale Serve is private to the tailnet. Do not use Tailscale Funnel unless you intentionally want public internet access.

Official reference: [Tailscale quickstart](https://tailscale.com/docs/how-to/quickstart), [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve), and [tailscale serve command](https://tailscale.com/docs/reference/tailscale-cli/serve)

## Option C: ngrok

Best for: quick temporary demos, class presentations, or testing a remote webhook-style URL.

High-level setup:

1. Create an ngrok account.
2. Install the ngrok Agent CLI.
3. Add your auth token.
4. Start the dashboard locally.
5. Start an HTTP tunnel to the local app port.
6. Share the generated HTTPS URL for the demo.
7. Stop the tunnel after the demo.

Example:

```powershell
ngrok config add-authtoken <YOUR_TOKEN>
ngrok http 5173
```

If using a production app entrypoint on port `8080`:

```powershell
ngrok http 8080
```

ngrok is excellent for temporary demos, but it is not the preferred permanent setup for this project unless you configure a stable endpoint and additional access controls.

Official reference: [ngrok Agent CLI quickstart](https://ngrok.com/docs/getting-started/) and [ngrok secure tunnels](https://ngrok.com/docs/guides/share-localhost/tunnels)

## Security Checklist

Before sharing any remote URL:

- Use a strong admin password and change demo credentials.
- Keep backend authentication required for every protected route.
- Enforce role-based access in the backend, not only the frontend.
- Keep PostgreSQL private. Do not expose port `5432`.
- Keep `.env`, API keys, database passwords, and tunnel tokens out of git.
- Use HTTPS through the tunnel or private network tooling.
- Restrict tunnel access when possible with Cloudflare Access, Tailscale ACLs, or ngrok Traffic Policy.
- Set `FRONTEND_ORIGIN` and CORS settings to the actual remote frontend origin.
- Use long random `SECRET_KEY` values in production-like demos.
- Review logs after a demo and rotate leaked tokens immediately if anything was shown on screen.
- Do not expose `/docs`, database admin tools, or debug endpoints publicly unless intentionally protected.

## Environment Notes

For a remote URL, update environment values carefully.

Backend example:

```text
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/hybrid_retail_bi
FRONTEND_ORIGIN=https://your-dashboard.example.com
SECRET_KEY=<long-random-secret>
```

Frontend example:

```text
VITE_API_BASE_URL=https://your-dashboard.example.com/api
```

For a one-host deployment, reverse proxy `/api` to FastAPI and everything else to the frontend build. This makes CORS easier and gives the tunnel one origin to expose.

## Manual Remote Access Acceptance Test

Use this checklist after configuring any option:

1. Open the remote dashboard URL from a device outside the local network.
2. Confirm the login screen appears.
3. Confirm invalid login fails.
4. Log in as Admin.
5. Open Overview, Inventory, Sales, Purchase Orders, Forecasting, AI Assistant, and Power BI Reports.
6. Confirm API calls succeed from the browser network panel.
7. Confirm direct database access from the remote device fails.
8. Confirm `localhost:5432` or the machine public IP does not expose PostgreSQL.
9. Confirm Store Manager users only see their assigned branch.
10. Stop the tunnel and confirm the remote URL no longer reaches the app.

## Recommended Portfolio Explanation

Use this line in the final case study:

> The system keeps the operational database local to reduce cloud cost and uses a secure tunnel or private network for remote dashboard access. Remote users can only reach the authenticated web app/API, never the database directly.

## Related Docs

- [Architecture](ARCHITECTURE.md)
- [Setup Guide](SETUP_GUIDE.md)
- [Case Study](CASE_STUDY.md)
- [Demo Script](DEMO_SCRIPT.md)
- [Backup And Restore](BACKUP_RESTORE.md)
- [QA Checklist](QA_CHECKLIST.md)
