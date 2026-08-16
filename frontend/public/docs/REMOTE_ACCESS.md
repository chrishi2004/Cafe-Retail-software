# Remote Access And Hybrid Local-First Deployment

This browser-accessible copy mirrors the full project guide at `docs/REMOTE_ACCESS.md`.

Core rules:

- The main PostgreSQL database stays local.
- Remote browsers access the dashboard/API only.
- Do not expose PostgreSQL port `5432`.
- App login and backend role checks remain required.

## Recommended Demo Option

Use Cloudflare Tunnel for a polished public portfolio URL.

```powershell
cloudflared tunnel --url http://localhost:5173
```

For a stable demo, create a named Cloudflare Tunnel and map it to a real hostname.

Official docs: https://developers.cloudflare.com/tunnel/

## Private Access Option

Use Tailscale when only trusted devices should access the dashboard.

```powershell
tailscale serve 5173
```

Tailscale Serve is private to your tailnet. Use ACLs to restrict users or devices.

Official docs: https://tailscale.com/docs/features/tailscale-serve

## Temporary Demo Option

Use ngrok for short-lived demos.

```powershell
ngrok config add-authtoken <YOUR_TOKEN>
ngrok http 5173
```

Official docs: https://ngrok.com/docs/getting-started/

## Security Checklist

- Change demo admin credentials before sharing a remote URL.
- Keep backend authentication enabled.
- Keep database credentials and tunnel tokens out of git.
- Use HTTPS or a private network.
- Keep PostgreSQL private.
- Set `FRONTEND_ORIGIN` and `VITE_API_BASE_URL` to the remote dashboard URL.
- Stop temporary tunnels when the demo is finished.

Full guide: `docs/REMOTE_ACCESS.md`.
