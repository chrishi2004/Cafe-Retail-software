# Demo Credentials

These accounts are created by the development seed script. They are for local development and portfolio demos only.

Default password for all demo users:

```text
RetailDemo@123
```

## Users

| Role | Email | Branch Scope |
|---|---|---|
| Admin | admin@hybridretail.test | All branches |
| Store Manager | manager.central@hybridretail.test | Central Market |
| Staff | staff.north@hybridretail.test | Northside Express |
| Staff | staff.lakeside@hybridretail.test | Lakeside Daily |
| Analyst | analyst@hybridretail.test | Read-only reporting |

Change or remove these credentials before using the app outside a local demo environment.

## Seeded Business Profile

The development seed also creates default billing and GST settings for the Hitech-competitive add-on path:

| Field | Demo Value |
|---|---|
| Legal Name | Hybrid Retail Demo Private Limited |
| Trade Name | Hybrid Retail Demo |
| PAN | ABCDE1234F |
| Primary GSTIN | 29ABCDE1234F1Z5 |
| Currency | INR |
| Invoice Sequence | INV-2026-00001 |

Seeded GST rates are `0%`, `5%`, `12%`, `18%`, and `28%`. Seeded payment modes are Cash, UPI, Card, Bank Transfer, and Credit.

GST, e-invoice, and e-way bill data in this project is for portfolio/demo use and must be reviewed by a CA/GST expert before production use.

## Related Docs

- [Setup Guide](SETUP_GUIDE.md)
- [Demo Script](DEMO_SCRIPT.md)
- [QA Checklist](QA_CHECKLIST.md)
