# Kalpvriksh Next.js / MongoDB Atlas rewrite

**Experimental migration, not a production replacement.** Frontend screens have been brought into Next.js and the new backend is native TypeScript, not a FastAPI proxy. The complete legacy backend has **not** been ported: unsupported operations return 501 `migration_pending`. See [the whole-product PRD](../../docs/nextjs/WEBSITE_PRD.md) and the exact original API/schema inventories. Do not deploy this over the installed Café.

## Isolated setup

Use Node 24 and a new MongoDB Atlas database whose name starts with `kalpvriksh_web_`. A standalone MongoDB server cannot provide the financial multi-document transactions required here. Production/staging must use separate databases, users, credentials and projects.

```bash
cd apps/web
npm ci
cp .env.example .env.local
# Privately edit .env.local: new Atlas URI/database and a random AUTH_SECRET.
# Generate AUTH_SECRET with: openssl rand -hex 32
# Fill unique real owner/Cafe cashier/Retail cashier emails and strong passwords.
# Never use NEXT_PUBLIC_* for credentials or database connection strings.
npm run bootstrap
```

Bootstrap is explicit and refuses any existing database records. It creates only a Kalpvriksh group, Café/Retail companies and branches, business profiles in non-GST mode, payment modes, separate numbering and three users. It does not create customers, products, stock or sales. The owner receives a one-time authenticator manual key in the trusted console; store it securely. Log in with the configured owner email/password and a current time-based code. Credentials/MFA from the old PostgreSQL system are not automatically imported.

```bash
npm run dev                  # local development, default port 3000
npm run typecheck
npm test                     # arithmetic, hashing, TOTP and configuration tests
npm run test:integration     # disposable MongoDB replica set; downloads test-only mongod
npm run build
npx playwright install chromium
npm run test:browser         # production Next server + browser + disposable MongoDB
npm start                    # production Next.js server, no Vite/FastAPI process
```

Keep `.env.local` outside version control. The bootstrap CLI uses Node's `--env-file`; Next loads `.env.local` for development/build/runtime. Configuration is validated lazily: a build does not need credentials, and `/api/health` returns 503 if the database is unavailable. A successful health response explicitly reports `production_parity:false`.

For Vercel, create a **separate project** with Root Directory `apps/web`, Next.js framework, Node 24, and private `MONGODB_URI`, `MONGODB_DB`, `AUTH_SECRET` values for each environment. Public API URLs may stay `/api`. Do not copy live customer secrets into previews. Do not bootstrap during builds or request startup. No deployment was performed by this change.

## Native backend boundary

Current native code covers scoped authentication/TOTP login/revocation, catalogue subsets, non-GST fully paid immediate checkout, integer-paise calculations, transaction/idempotency and conditional stock deduction, read-only Café receipts/history, simple native-sale Café reporting/CSV, group turnover, adjustments and current-day closing. MongoDB unique indexes are installed only by the explicit bootstrap.

Pending: complete response/filter/pagination parity; GST, partial/credit/change/refund/ledger/draft behavior; MFA management and step-up; purchase/receiving/reservation/costing; table/session/kitchen/QR/cloud state machines; full Retail/consolidated reports; AI/forecast/BI/provider parity; migration/import/backup/restore and physical acceptance. Pages using pending APIs show errors rather than simulated data. Preserved original source is available for the remaining ports.

Atlas connectivity is required to bill. This new web architecture does not retain the original LAN-only offline guarantee. The existing PostgreSQL production installation and release branches remain unchanged.

## Validation record

See [the conversion report](../../docs/nextjs/CONVERSION_REPORT.md) for actual commands/results, unresolved integration-environment blockers and changed-file scope. Do not interpret build success as complete backend parity or production approval.
