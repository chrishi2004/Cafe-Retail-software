# Kalpvriksh Web

Kalpvriksh is a single hosted Café and Retail operations product. The browser,
authenticated API, public QR ordering API and business services are delivered by
one Next.js application on Vercel. MongoDB Atlas is the only active database.

```text
Browser / customer QR
        |
        v
Next.js on Vercel (React UI + TypeScript API)
        |
        v
MongoDB Atlas
```

The production application lives in [`apps/web`](apps/web). There is no active
FastAPI, PostgreSQL, Alembic, Vite, Supabase coordination or Local Hub runtime in
this repository.

The complete former Local Hub and hybrid architecture is preserved privately in
[`Cafe-Retail-software-local-hub-archive`](https://github.com/chrishi2004/Cafe-Retail-software-local-hub-archive),
tagged `local-hub-final-2026-11-19`.

## Product areas

- Retail POS, inventory, purchasing, customer credit, forecasting and exports
- Café POS, menu, tables, QR ordering, kitchen flow, receipts and closing
- Shared staff access, MFA, audit history, expenses, reporting and profit/loss
- Multi-venture and branch isolation enforced by the API

## Development

```bash
cd apps/web
npm ci
cp .env.example .env.local
npm run typecheck
npm test
npm run test:integration
npm run build
```

Do not run `npm run bootstrap` against an existing production database. Keep the
production `MONGODB_URI`, `MONGODB_DB` and `AUTH_SECRET` unchanged during normal
deployments.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Backup and recovery](docs/BACKUP_AND_RECOVERY.md)
- [Product readiness](docs/PRODUCT_READINESS.md)
- [Profit and loss accounting boundary](docs/PROFIT_AND_LOSS.md)
- [Reporting exports](docs/REPORTING_EXPORTS.md)
