# Deployment

## Vercel configuration

- Repository: `chrishi2004/Cafe-Retail-software`
- Production branch: `main`
- Root Directory: `apps/web`
- Runtime: Node.js 24
- Build command: `npm run build`
- Output: Next.js default

Configure `MONGODB_URI`, `MONGODB_DB` and `AUTH_SECRET` as private environment
variables. Never place credentials in `NEXT_PUBLIC_*` variables.

## Safe release sequence

1. Review the exact commit and obtain a green Web CI result.
2. Deploy a preview with a non-production Atlas database.
3. Run browser and business acceptance tests on the preview.
4. Verify a recent production backup and restore drill.
5. Stage a production build without assigning the shop domain.
6. Smoke-test login, Café POS, Retail POS, QR ordering and health.
7. Promote the exact staged build.
8. Scan runtime errors and retain the prior deployment as rollback candidate.

Never bootstrap, reset, reseed, rotate `AUTH_SECRET`, or replace the Atlas
database as part of a normal code deployment.
