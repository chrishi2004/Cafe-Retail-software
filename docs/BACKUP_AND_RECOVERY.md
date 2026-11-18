# Backup and recovery

The live Atlas database is the authority for invoices, payments, stock, orders,
staff access and audit records. A source-code rollback does not roll back data.

Before every production release:

1. Create or verify a recent Atlas snapshot or encrypted `mongodump`.
2. Copy it to storage independent of the Atlas project and developer laptop.
3. Restore it into a disposable database named `kalpvriksh_web_restore_*`.
4. Verify users, invoice counts, payments, inventory, orders and indexes.
5. Record the backup timestamp and the accepted data-loss boundary.

If a release writes new-format financial data, pause writes and forward-fix or
reconcile before rolling code back. Never bootstrap or drop the production
database during recovery.
