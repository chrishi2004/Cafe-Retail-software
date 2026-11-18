# Kalpvriksh Next.js application

This directory is the complete hosted product: React pages, Next.js Route
Handlers, TypeScript business services and MongoDB Atlas access.

## Runtime

- Node.js 24
- Next.js and React
- MongoDB Atlas with multi-document transaction support
- Vercel Root Directory: `apps/web`

## Required private environment variables

- `MONGODB_URI`
- `MONGODB_DB` (must match `kalpvriksh_web_*`)
- `AUTH_SECRET` (at least 32 random characters)

Bootstrap variables in `.env.example` are used only for a new, empty database.
Never bootstrap an existing shop database and never rotate `AUTH_SECRET` during a
normal deployment.

## Commands

```bash
npm ci
npm run typecheck
npm test
npm run test:integration
npm run build
npm run test:browser
```

Tests use disposable MongoDB replica sets and must never point at production.

## New database setup only

```bash
cp .env.example .env.local
npm run bootstrap
```

Bootstrap creates the business group, Café/Retail ventures, branches, owner and
cashier accounts. It prints the owner's TOTP setup key and recovery codes once.

## Trusted MFA recovery

```bash
npm run mfa -- begin --email OWNER_EMAIL
npm run mfa -- confirm --email OWNER_EMAIL
```

Run these only from a trusted terminal configured with the intended Atlas
database and the matching `AUTH_SECRET`.

## Deployment

Deploy through a preview first. Validate the preview against a non-production
database, stage the reviewed production build without assigning the shop domain,
run acceptance checks, and then promote that exact build. See
[`docs/DEPLOYMENT.md`](../../docs/DEPLOYMENT.md).
