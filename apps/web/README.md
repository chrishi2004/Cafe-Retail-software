# Kalpvriksh — Next.js + MongoDB Atlas

The hosted Retail/Café website lives entirely in **`apps/web`**. Next.js serves the pages and TypeScript API handlers in one deployment. The root `frontend/` and `backend/` directories preserve the original local-first product; they are not deployed by this Vercel project.

Native web workflows include inventory/sales/purchase dashboards, POS, customer credit/ledgers, GST calculations, purchase receiving, Café orders/kitchen/tables, restricted customer QR ordering, receipts, closing, forecasts, saved deterministic assistant chats and exports. Read the [implementation report](../../docs/nextjs/NATIVE_COMPLETION_REPORT.md) for evidence, intentional legacy-interface changes and production gates. This is not a claim of full legacy parity or physical acceptance.

## First setup — new database only

Use Node 24 and an Atlas database named `kalpvriksh_web_*`. Never point at an old customer database. A standalone MongoDB server cannot support the multi-document financial transactions used here.

```bash
cd apps/web
npm ci
cp -n .env.example .env.local
```

Privately edit `.env.local`:

- `MONGODB_URI`: Atlas database username/password connection string; URL-encode special password characters.
- `MONGODB_DB`: for example `kalpvriksh_web_staging`.
- `AUTH_SECRET`: a random value of at least 32 characters, generated with `openssl rand -hex 32`. **Use exactly the same value in local setup and Vercel.** It protects sessions and encrypted MFA secrets.
- Six `BOOTSTRAP_*` email/password fields: three distinct valid emails; passwords of at least 12 characters.

```bash
npm run bootstrap
```

Bootstrap refuses any database that already contains records. It creates only the group, Café/Retail companies/branches, non-GST business profiles, separate numbering, payment modes and owner/two cashier accounts. It does not seed products, customers, stock or sales. It prints the owner's **time-based authenticator setup key and recovery codes once**. Keep that output private. In Google Authenticator, choose **+ → Enter a setup key → Time based** and enter the printed key, not `AUTH_SECRET`.

All users share `/login`. The owner uses email, password and authenticator/recovery code. The Café cashier opens Café POS; the Retail cashier opens Retail POS. Cashiers do not need TOTP unless MFA is intentionally enabled for those accounts.

**Existing deployment:** keep its same database and `AUTH_SECRET`. Do not rerun bootstrap after a code update. New collections/indexes are additive; existing records are not reseeded.

## Lost authenticator — trusted terminal only

After configuring the same private database and `AUTH_SECRET` in `.env.local`:

```bash
npm run mfa -- begin --email YOUR_OWNER_EMAIL
```

Add the newly printed key to Authenticator and save the new recovery codes. Run `begin` only once for that enrollment. Existing MFA remains valid until the new key is confirmed.

```bash
npm run mfa -- confirm --email YOUR_OWNER_EMAIL
```

Enter the current six-digit code when prompted. Confirmation replaces the secret, revokes prior sessions and consumes that code. Wait for the next phone code before logging in. Enrollment expires after 15 minutes. Do not print or share `.env.local`.

## Development and validation

```bash
npm run dev
npm run typecheck
npm test
npm run test:integration
npm run build
npx playwright install chromium
npm run test:browser
npm start
```

Tests use disposable local replica sets, never the configured customer Atlas database. `test:browser` starts the production Next build. See the report for actual test results and the inherited Python date-boundary failure.

## Vercel

| Setting | Value |
| --- | --- |
| Repository branch | `main` |
| Root Directory | **`apps/web`** |
| Framework | Next.js |
| Runtime | Node 24 |
| Build | `npm run build` |
| Output directory | Next.js default |
| Private environment | `MONGODB_URI`, `MONGODB_DB`, `AUTH_SECRET` |

Public API base URLs can stay `/api`. Do not put credentials in `NEXT_PUBLIC_*`, bootstrap during builds, or copy production credentials into previews. Bootstrap/MFA console tasks run from a trusted local terminal against the intended Atlas database. Accounts and old PostgreSQL MFA are not automatically imported.

Atlas connectivity is required for billing and QR ordering. Payments are recorded collection entries; automatic payment-provider charging/refunding is not implied. Physical receipt output, backups/restore, statutory GST documents and production acceptance require separate verification. `/api/health` deliberately retains `production_parity:false`.
