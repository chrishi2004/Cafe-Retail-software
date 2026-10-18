"""Read-only browser-audit probe, restricted to disposable PostgreSQL databases."""
import json
import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

url = make_url(os.environ['CAFE_AUDIT_DATABASE_URL'])
if url.get_backend_name() != 'postgresql' or not url.database.startswith('cafe_test_'):
    raise SystemExit('Acceptance probes require a disposable cafe_test_* PostgreSQL database.')
tables = ('cafe_orders', 'invoices', 'invoice_items', 'invoice_payments', 'invoice_sequences',
          'inventory', 'stock_movements', 'sales', 'sale_items', 'customer_ledger_entries', 'business_day_closures')
engine = create_engine(url)
with engine.connect() as db:
    result = {table: list(db.execute(text(f'SELECT row_to_json(t)::text FROM {table} t ORDER BY 1')).scalars()) for table in tables}
engine.dispose()
print(json.dumps(result, sort_keys=True))
