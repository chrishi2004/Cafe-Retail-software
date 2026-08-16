# Screenshots Guide

## Purpose

This guide defines the screenshot set for the final portfolio README, GitHub repository, case study, and interview demo.

The repository already includes:

```text
powerbi/screenshots/
```

Use that folder for Power BI screenshots. App screenshots can be stored in:

```text
docs/screenshots/
```

If you prefer to keep all images together, use:

```text
powerbi/screenshots/
```

for Power BI only and create `docs/screenshots/` for application screenshots.

## Recommended Screenshot List

| Screenshot | Suggested File Name | Purpose |
| --- | --- | --- |
| Login page | `01-login.png` | Shows authenticated dashboard entry. |
| Overview dashboard | `02-overview-dashboard.png` | Main executive dashboard. |
| Sales Summary | `03-sales-summary.png` | Revenue, profit, trends, filters. |
| Inventory table | `04-inventory.png` | Remote stock visibility and filters. |
| Low Stock and Reorder | `05-low-stock-reorder.png` | Reorder recommendation engine. |
| Purchase Order detail | `06-purchase-order-received.png` | Draft-to-received lifecycle proof. |
| Forecasting page | `07-forecasting.png` | Historical vs forecast chart. |
| AI Assistant | `08-ai-assistant.png` | Database-backed business answer. |
| Power BI Reports page | `09-power-bi-page.png` | Reporting support in the app. |
| Power BI Desktop report | `powerbi/screenshots/executive-overview.png` | Executive BI presentation. |
| Architecture diagram | `10-architecture.png` | Hybrid local-first design. |

## Capture Guidelines

- Use seeded demo data so dashboards look realistic.
- Avoid showing real passwords, API keys, tunnel tokens, or database credentials.
- Use the Admin account for full dashboard screenshots.
- Use the Store Manager account for one branch-scoped screenshot if you want to prove RBAC.
- Prefer a 1440px wide desktop viewport for portfolio screenshots.
- Capture one tablet-width screenshot if you want to show responsive behavior.
- Do not capture `.env` files, terminal secrets, or private tunnel URLs.

## Suggested README Image Placement

After screenshots are captured, add a short visual section to README:

```markdown
## Screenshots

![Overview dashboard](docs/screenshots/02-overview-dashboard.png)
![Low-stock reorder page](docs/screenshots/05-low-stock-reorder.png)
![AI assistant](docs/screenshots/08-ai-assistant.png)
```

Use relative Markdown links for GitHub display. Keep large image files reasonably compressed.

## Power BI Screenshot Plan

Store Power BI images in:

```text
powerbi/screenshots/
```

Recommended files:

- `executive-overview.png`
- `sales-performance.png`
- `inventory-health.png`
- `supplier-purchase-orders.png`
- `forecast-recommendations.png`

## Demo Recording Checklist

Before taking screenshots or recording:

1. Run migrations.
2. Reset seed data.
3. Start backend.
4. Start frontend.
5. Log in as Admin.
6. Confirm Overview, Sales, Inventory, Low Stock, Purchase Orders, Forecasting, AI Assistant, and Power BI Reports load.
7. Close any terminal window showing secrets.
8. Use browser zoom at 100 percent.

## Related Docs

- [Demo Script](DEMO_SCRIPT.md)
- [Case Study](CASE_STUDY.md)
- [Architecture](ARCHITECTURE.md)
- [Power BI Setup](POWER_BI_SETUP.md)
- [QA Checklist](QA_CHECKLIST.md)
