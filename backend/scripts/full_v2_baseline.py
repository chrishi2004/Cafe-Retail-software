"""Read-only reconciliation on an explicitly isolated PostgreSQL staging copy only.

Does not bootstrap, migrate, restore, log in, or run a financial operation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


REQUIRED = {'business_groups', 'companies', 'branches', 'users', 'menu_items',
            'cafe_orders', 'invoices', 'invoice_items', 'invoice_payments',
            'invoice_sequences', 'inventory', 'stock_movements', 'business_day_closures',
            'business_profiles', 'gst_registrations', 'customers', 'payment_modes'}


def staging_url():
    raw = os.environ.get('F0_STAGING_DATABASE_URL', '')
    if not raw:
        raise RuntimeError('F0_STAGING_DATABASE_URL must explicitly select an isolated staging database.')
    url = make_url(raw)
    if url.get_backend_name() != 'postgresql' or not (url.database or '').startswith(
            ('cafe_restore_', 'cafe_test_', 'kalpvrik_staging_')):
        raise RuntimeError('Only isolated PostgreSQL staging database names are allowed.')
    if os.environ.get('F0_STAGING_ACK') != 'isolated-not-live':
        raise RuntimeError('Set F0_STAGING_ACK=isolated-not-live only after verifying infrastructure isolation.')
    for key in ('LOCAL_DATABASE_URL', 'LOCAL_BACKUP_DATABASE_URL', 'DATABASE_URL'):
        if os.environ.get(key):
            live = make_url(os.environ[key])
            loopbacks = {'localhost', '127.0.0.1', '::1', None}
            stage_host = 'loopback' if url.host in loopbacks else url.host
            live_host = 'loopback' if live.host in loopbacks else live.host
            if (stage_host, url.port or 5432, url.database) == (live_host, live.port or 5432, live.database):
                raise RuntimeError('Staging target matches a configured application/backup database.')
    return url


def fingerprint(rows):
    digest = hashlib.sha256()
    count = 0
    for row in rows:
        digest.update(row.encode('utf-8'))
        digest.update(b'\n')
        count += 1
    return {'count': count, 'sha256': digest.hexdigest()}


def capture(url):
    engine = create_engine(url, isolation_level='REPEATABLE READ')
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text('SET TRANSACTION READ ONLY'))
            connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
            connection.execute(text("SET LOCAL statement_timeout = '120s'"))
            tables = sorted(inspect(connection).get_table_names(schema='public'))
            if not REQUIRED.issubset(tables):
                raise RuntimeError('Incomplete Cafe V1 schema: ' + ', '.join(sorted(REQUIRED - set(tables))))
            quote = connection.dialect.identifier_preparer.quote
            result = {'format': 1, 'tables': {}, 'columns': {}, 'views': {}, 'sequences': {}, 'totals': {}, 'revisions':
                      sorted(connection.execute(text('SELECT version_num FROM alembic_version')).scalars())}
            for table in tables:
                if table == 'alembic_version':
                    continue
                result['columns'][table] = {column['name']: {
                    'type': str(column['type']), 'nullable': column['nullable'],
                    'default': column['default']} for column in inspect(connection).get_columns(table, schema='public')}
                # Canonical JSONB order, UTC timestamps, duplicate-preserving sorted rows.
                rows = connection.execution_options(stream_results=True).execute(text(
                    f'SELECT to_jsonb(t)::text FROM public.{quote(table)} t ORDER BY 1'))
                result['tables'][table] = fingerprint(row[0] for row in rows)
            for view in sorted(inspect(connection).get_view_names(schema='public')):
                definition = inspect(connection).get_view_definition(view, schema='public')
                result['views'][view] = hashlib.sha256(definition.encode()).hexdigest()
            sequence_names = connection.execute(text(
                "SELECT sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename")).scalars().all()
            for name in sequence_names:
                # SELECT never calls nextval/setval. Freeze writers while collecting evidence:
                # PostgreSQL sequences are not MVCC snapshots.
                row = connection.execute(text(f'SELECT last_value, is_called FROM public.{quote(name)}')).one()
                result['sequences'][name] = list(row)
            for name, sql in {
                'invoices': """SELECT company_id, branch_id,
                    (invoice_date AT TIME ZONE 'Asia/Kolkata')::date::text AS business_date,
                    status, count(*) AS count, sum(grand_total)::text AS grand_total,
                    sum(paid_amount)::text AS paid_amount, sum(balance_due)::text AS balance_due,
                    sum(cgst_total+sgst_total+igst_total+cess_total)::text AS tax
                    FROM invoices GROUP BY 1,2,3,4 ORDER BY 1,2,3,4""",
                'payments': """SELECT i.company_id, i.branch_id,
                    (p.payment_datetime AT TIME ZONE 'Asia/Kolkata')::date::text AS business_date,
                    p.payment_mode_id, p.is_credit_marker, count(*) AS count, sum(p.amount)::text AS amount
                    FROM invoice_payments p JOIN invoices i ON i.id=p.invoice_id
                    GROUP BY 1,2,3,4,5 ORDER BY 1,2,3,4,5""",
                'closing': """SELECT company_id, branch_id, business_date::text, status,
                    opening_cash::text, expected_cash::text, counted_cash::text,
                    non_cash_total::text, variance::text FROM business_day_closures
                    ORDER BY company_id, branch_id, business_date""",
                'stock': """SELECT company_id, branch_id, product_id, quantity_on_hand::text,
                    quantity_reserved::text, quantity_on_order::text FROM inventory
                    ORDER BY company_id, branch_id, product_id""",
            }.items():
                result['totals'][name] = [dict(row) for row in connection.execute(text(sql)).mappings()]
            return result
    finally:
        engine.dispose()


def compare(before, after):
    if before.get('format') != 1 or after.get('format') != 1:
        raise RuntimeError('Unsupported baseline evidence format.')
    differences = []
    for kind in ('tables', 'sequences'):
        for name, value in before[kind].items():
            if after[kind].get(name) != value:
                differences.append(f'{kind}.{name}')
    for table, columns in before.get('columns', {}).items():
        for column, definition in columns.items():
            if after.get('columns', {}).get(table, {}).get(column) != definition:
                differences.append(f'columns.{table}.{column}')
    for name, definition in before.get('views', {}).items():
        if after.get('views', {}).get(name) != definition:
            differences.append(f'views.{name}')
    if before.get('totals', {}) != after.get('totals', {}):
        differences.append('totals')
    if differences:
        raise RuntimeError('Historical data changed: ' + ', '.join(differences))
    return {'historical_data_unchanged': True,
            'revisions_before': before['revisions'], 'revisions_after': after['revisions'],
            'added_tables': sorted(set(after['tables']) - set(before['tables']))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    snapshot = commands.add_parser('capture')
    snapshot.add_argument('--output', type=Path, required=True)
    diff = commands.add_parser('compare')
    diff.add_argument('--before', type=Path, required=True)
    diff.add_argument('--after', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'compare':
        print(json.dumps(compare(json.loads(args.before.read_text()), json.loads(args.after.read_text())), indent=2))
    else:
        evidence = capture(staging_url())
        # Evidence is append-only: refuse overwriting an existing baseline.
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(evidence, stream, indent=2, sort_keys=True)
            stream.write('\n')
        print('Staging snapshot saved; no database writes were executed.')


if __name__ == '__main__':
    main()
