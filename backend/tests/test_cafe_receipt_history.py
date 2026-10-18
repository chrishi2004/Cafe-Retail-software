from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, select

from app.models import Branch, Company, Invoice, InvoicePayment, Inventory, StockMovement
from app.services.business_day import business_today
from tests.multi_venture_fixtures import login_headers
from tests.p7_fixtures import cafe_headers
from tests.test_cafe_v1 import payload, sale, seed_cashier


def issue(client, factory):
    ids = seed_cashier(factory)
    headers = login_headers(client, 'cashier@example.test')
    with factory() as db:
        db.get(Company, ids['cafe_company']).trade_name = 'Configured Café & Kitchen'
        db.get(Branch, ids['cafe_branch']).name = 'Configured Counter'
        db.commit()
    result = sale(client, headers, payload(ids))
    assert result.status_code == 200, result.text
    return ids, headers, result.json()['receipt']


def test_history_and_reprint_are_read_only_and_use_configured_branding(client, db_session_factory):
    ids, headers, receipt = issue(client, db_session_factory)
    with db_session_factory() as db:
        before = {
            model.__tablename__: [dict(row._mapping) for row in db.execute(select(model.__table__))]
            for model in (Invoice, InvoicePayment, Inventory, StockMovement)
        }
        engine = db.get_bind()
    writes = []
    def track(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().split(None, 1)[0].upper() in {'INSERT', 'UPDATE', 'DELETE'}:
            writes.append(statement)
    event.listen(engine, 'before_cursor_execute', track)
    try:
        for _ in range(3):
            history = client.get('/api/cafe/billing/invoices', headers=headers)
            assert history.status_code == 200, history.text
            assert history.json()['total'] == 1
            assert history.json()['items'][0]['invoice_id'] == receipt['invoice_id']
            reprint = client.get(f"/api/cafe/billing/invoices/{receipt['invoice_id']}/receipt", headers=headers)
            assert reprint.status_code == 200, reprint.text
            assert reprint.json() == receipt
            assert reprint.json()['cafe_name'] == 'Configured Café & Kitchen'
            assert reprint.json()['branch_name'] == 'Configured Counter'
            assert reprint.json()['issued_at'].endswith(('Z', '+00:00'))
            assert all(key in reprint.json()['items'][0] for key in ('name', 'quantity', 'unit_price', 'line_total'))
    finally:
        event.remove(engine, 'before_cursor_execute', track)
    assert writes == []
    with db_session_factory() as db:
        after = {model.__tablename__: [dict(row._mapping) for row in db.execute(select(model.__table__))]
                 for model in (Invoice, InvoicePayment, Inventory, StockMovement)}
    assert after == before
    # Printing never consumes or rotates the checkout key.
    replay = sale(client, headers, payload(ids))
    assert replay.status_code == 200 and replay.json()['idempotent_replay']
    assert replay.json()['receipt']['invoice_id'] == receipt['invoice_id']


def test_history_and_receipt_enforce_roles_company_branch_and_bounds(client, db_session_factory):
    ids, cashier, receipt = issue(client, db_session_factory)
    with db_session_factory() as db:
        source = db.get(Invoice, receipt['invoice_id'])
        copy = {column.name: getattr(source, column.name) for column in Invoice.__table__.columns
                if column.name not in {'id', 'invoice_number', 'source_id', 'billing_idempotency_key_hash'}}
        second = Invoice(**{**copy, 'branch_id': ids['cafe_second_branch'], 'invoice_number': 'ANNEX-001',
                            'source_id': 'annex-source'})
        retail = Invoice(**{**copy, 'company_id': 1, 'branch_id': ids['retail_branch'],
                            'invoice_number': 'RETAIL-001', 'source_type': None, 'source_id': None})
        db.add_all([second, retail]); db.commit()
        second_id, retail_id = second.id, retail.id
    history = client.get('/api/cafe/billing/invoices', headers=cashier).json()
    assert history['total'] == 1
    assert {item['branch_id'] for item in history['items']} == {ids['cafe_branch']}
    assert client.get(f'/api/cafe/billing/invoices/{second_id}/receipt', headers=cashier).status_code == 404
    assert client.get(f'/api/cafe/billing/invoices?branch_id={ids["cafe_second_branch"]}', headers=cashier).status_code == 403
    owner = cafe_headers(client, 'admin')
    assert client.get('/api/cafe/billing/invoices', headers=owner).json()['total'] == 2
    assert client.get(f'/api/cafe/billing/invoices/{retail_id}/receipt', headers=owner).status_code == 404
    assert client.get('/api/cafe/billing/invoices', headers=cafe_headers(client, 'retail_admin')).status_code == 403
    for role in ('kitchen', 'analyst'):
        denied = cafe_headers(client, role)
        assert client.get('/api/cafe/billing/invoices', headers=denied).status_code == 403
        assert client.get(f"/api/cafe/billing/invoices/{receipt['invoice_id']}/receipt", headers=denied).status_code == 403
    assert client.get('/api/cafe/billing/invoices').status_code == 401
    for query in ('limit=101', 'limit=0', 'offset=-1', 'search=' + 'a' * 101):
        assert client.get('/api/cafe/billing/invoices?' + query, headers=owner).status_code == 422


def test_history_search_pagination_date_range_and_outstanding_receipts(client, db_session_factory):
    ids, headers, receipt = issue(client, db_session_factory)
    with db_session_factory() as db:
        invoice = db.get(Invoice, receipt['invoice_id'])
        invoice.paid_amount = Decimal('100')
        invoice.balance_due = invoice.grand_total - Decimal('100')
        db.commit()
    number = receipt['invoice_number']
    today = business_today()
    for query, total in ((f'search={number}', 1), ('search=missing', 0), ('search=%25', 0),
                         (f'start_date={today}&end_date={today}', 1),
                         (f'end_date={today - timedelta(days=1)}', 0), ('offset=1&limit=1', 1)):
        result = client.get('/api/cafe/billing/invoices?' + query, headers=headers)
        assert result.status_code == 200, result.text
        assert result.json()['total'] == total
        if 'offset=1' in query:
            assert result.json()['items'] == []
    assert client.get(f'/api/cafe/billing/invoices?start_date={today}&end_date={today-timedelta(days=1)}', headers=headers).status_code == 400
    outstanding = client.get(f"/api/cafe/billing/invoices/{receipt['invoice_id']}/receipt", headers=headers).json()
    assert outstanding['paid_amount'] == '100.00'
    assert Decimal(outstanding['balance_due']) > 0
