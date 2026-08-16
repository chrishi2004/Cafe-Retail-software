# P4 Phase Report: GST-Ready, Non-GST-Default Configuration

## Status

- Phase: P4
- Status: Complete
- Date: 2026-08-13
- Base: verified P3 `main`
- Verified implementation head: `fcee5f47afd25240f830172fdd73d4c2f4dd39d6`
- Merge commit: `20f30a2fb086aa1723ca6f4765099e57a78cc992`
- Local Alembic head: `20260813_0010`
- Cloud Alembic history: unchanged and separate

## Implemented Scope

- Added venture tax registration state, effective date, customer-detail privacy mode, B2B GST flag, and GST-report customer flag.
- Changed current operational defaults to unregistered / Non-GST for Retail and Cafe.
- Preserved HSN/SAC and reference tax metadata internally while marking demo GST registrations inactive/reference-only.
- Added Non-GST invoice sequences/templates for active ventures without creating a separate Cafe billing engine.
- Added server-derived tax-operation API and Super Admin-only settings/activation controls.
- Added recent step-up, registration, GSTIN format, legal identity, state, effective-date, invoice-sequence, invoice-template, explicit professional-review acknowledgement, typed confirmation, and no-backdating prerequisites for GST activation.
- Added effective-date enforcement so a client cannot force GST before activation or force Non-GST after the effective date.
- Protected the legacy business-profile endpoint from changing tax mode outside the guarded workflow while preserving safe first-time Non-GST profile creation.
- Added owner-only combined BusinessGroup turnover monitoring explicitly labelled as a review aid, not legal advice.
- Added canonical P4 development seed wrapper that leaves both ventures operating Non-GST.
- Added authoritative Retail/Cafe tax-operation settings UI with masked GSTIN and Super Admin-only guarded activation controls.
- Added Super Admin per-venture and combined turnover review cards.

## Verification Result

The exact P4 implementation head `fcee5f47afd25240f830172fdd73d4c2f4dd39d6` passed all P4 and inherited GitHub Actions gates before merge:

- P4 Non-GST Operation Verification: run `31686376853` passed backend and frontend jobs.
  - PostgreSQL migration to local head `20260813_0010` passed.
  - Local/cloud migration history separation passed.
  - Canonical P4 Retail/Cafe seed passed.
  - P4 release-blocking tax/privacy/activation plus invoice/POS/auth/isolation regression block passed.
  - Complete backend regression passed.
  - Backend compile passed.
  - Frontend portal-boundary verifier, typecheck, and production build passed.
- HC1 Verification: run `31686376867` passed.
- P1 Multi-Venture Schema Verification: run `31686376802` passed.
- P2 Scope Enforcement Verification: run `31686376827` passed after making the inherited migration assertion compatible with later local migrations.
- P3 Portal And Venture User Verification: run `31686376878` passed after making the inherited migration assertion compatible with later local migrations.

## Security And Compatibility Repairs Proven During Verification

- Client-forced GST is rejected while a venture is Non-GST.
- Client-forced Non-GST is rejected on/after a valid GST effective date.
- Historical Non-GST invoices remain unchanged after later GST activation.
- Customer-facing Non-GST output applies zero GST and does not expose GSTIN.
- HSN/SAC and reference GST rate metadata remain available internally.
- Normal Admin, Manager, Staff, Analyst, Cafe Partner, Order Taker, and Kitchen roles cannot activate GST.
- Super Admin activation requires recent step-up, explicit review acknowledgement, typed confirmation, complete prerequisites, and a non-backdated effective date.
- Legacy business-setting tests and invoice/POS regression tests were converted to safe Non-GST defaults; GST arithmetic tests use an explicit activated test fixture rather than reopening the API bypass.
- P2/P3 inherited workflows now verify their migrations remain in history instead of incorrectly requiring them to remain the repository head forever.

## Boundaries

- No hard-coded GST registration threshold or automatic legal determination.
- No retroactive conversion of historical Non-GST invoices.
- No live GST portal, e-invoice, or e-way integration.
- P5 owns Cafe menu, tables, QR tokens, and table sessions. P4 does not accept public customer orders.
