from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.models import (
    BusinessDayClosure, CafeOrder, Inventory, Invoice, InvoicePayment, PaymentMode,
    PaymentModeType, StockMovement, User, UserRole,
)
from app.services.business_day import business_bounds, business_today
from tests.multi_venture_fixtures import login_headers
from tests.p7_fixtures import cafe_headers
from tests.p8_fixtures import seed_p8


def seed_cashier(factory):
    ids = seed_p8(factory)
    with factory() as db:
        db.add(User(business_group_id=1, company_id=ids['cafe_company'], branch_id=ids['cafe_branch'],
                    name='Cashier', email='cashier@example.test', role=UserRole.STAFF,
                    password_hash=hash_password('RetailDemo@123')))
        card = PaymentMode(company_id=ids['cafe_company'], name='Card terminal', mode_type=PaymentModeType.CARD)
        db.add(card); db.commit(); ids['card_mode'] = card.id
    return ids


def payload(ids, mode='cash_mode', quantity=2):
    return {'branch_id': ids['cafe_branch'], 'order_type': 'counter',
            'items': [{'menu_item_public_id': ids['menu_item_public_id'], 'quantity': quantity}],
            'payment_mode_id': ids[mode], 'reference_number': 'V1-PAY-123'}


def sale(client, headers, body, key='cafe-v1-sale-001'):
    return client.post('/api/cafe/billing/pos/checkout', headers={**headers, 'Idempotency-Key': key}, json=body)


@pytest.mark.parametrize('payment,order_type', [('cash_mode', 'counter'), ('upi_mode', 'takeaway'), ('card_mode', 'counter')])
def test_cashier_checkout_uses_existing_invoice_stock_and_safe_replay(client, db_session_factory, payment, order_type):
    ids = seed_cashier(db_session_factory)
    headers = login_headers(client, 'cashier@example.test')
    body = {**payload(ids, payment), 'order_type': order_type}
    assert client.get('/api/cafe/menu/items', headers=headers).status_code == 200
    branches = client.get('/api/branches', headers=headers).json()
    assert [b['id'] for b in branches] == [ids['cafe_branch']]
    with db_session_factory() as db:
        before = db.scalar(select(Inventory.quantity_on_hand).where(Inventory.product_id == ids['cafe_product']))
    first = sale(client, headers, body)
    assert first.status_code == 200, first.text
    receipt = first.json()['receipt']
    assert receipt['paid_amount'] == receipt['grand_total']
    assert receipt['balance_due'] == '0.00'
    assert first.json()['closed']
    replay = sale(client, headers, body)
    assert replay.status_code == 200, replay.text
    assert replay.json()['idempotent_replay']
    assert replay.json()['receipt']['invoice_id'] == receipt['invoice_id']
    assert sale(client, headers, {**body, 'order_type': 'takeaway' if order_type == 'counter' else 'counter'}).status_code == 409
    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 1
        assert db.scalar(select(func.count()).select_from(CafeOrder)) == 1
        assert db.scalar(select(Inventory.quantity_on_hand).where(Inventory.product_id == ids['cafe_product'])) == before - 2
        assert db.scalar(select(func.sum(StockMovement.quantity_change))) == -2
    today = business_today()
    report = client.get(f'/api/dashboard/cafe?start_date={today}&end_date={today}', headers=cafe_headers(client, 'admin')).json()
    assert report['kpis']['order_count'] == 1
    assert report['kpis']['average_bill_value'] == receipt['grand_total']
    assert Decimal(report['top_selling_items'][0]['units_sold']) == 2
    # A fresh next-customer key creates a distinct invoice.
    second = sale(client, headers, {**body, 'items': [{**body['items'][0], 'quantity': 1}]}, 'cafe-v1-next-002')
    assert second.status_code == 200, second.text
    assert second.json()['receipt']['invoice_id'] != receipt['invoice_id']


def test_checkout_failure_rolls_back_order_invoice_payment_and_stock(client, db_session_factory, monkeypatch):
    ids = seed_cashier(db_session_factory)
    headers = login_headers(client, 'cashier@example.test')
    from app.services import cafe_billing
    original = cafe_billing.add_invoice_payments
    def fail(*args, **kwargs):
        raise RuntimeError('checkout interrupted')
    monkeypatch.setattr(cafe_billing, 'add_invoice_payments', fail)
    with pytest.raises(RuntimeError, match='interrupted'):
        sale(client, headers, payload(ids))
    with db_session_factory() as db:
        for model in (CafeOrder, Invoice, InvoicePayment, StockMovement):
            assert db.scalar(select(func.count()).select_from(model)) == 0
    monkeypatch.setattr(cafe_billing, 'add_invoice_payments', original)
    assert sale(client, headers, payload(ids)).status_code == 200


def test_owner_closing_refreshes_live_totals_and_logout_does_not_close(client, db_session_factory):
    ids = seed_cashier(db_session_factory)
    owner = cafe_headers(client, 'admin')
    cashier = login_headers(client, 'cashier@example.test')
    today = business_today().isoformat()
    create = {'branch_id': ids['cafe_branch'], 'business_date': today, 'opening_cash': '100'}
    opened = client.post('/api/governance/closings', headers=owner, json=create)
    assert opened.status_code == 200, opened.text
    row = opened.json()
    cash = sale(client, cashier, payload(ids), 'v1-close-cash').json()['receipt']['grand_total']
    upi = sale(client, cashier, payload(ids, 'upi_mode', 1), 'v1-close-upi').json()['receipt']['grand_total']
    assert client.post('/api/auth/logout', headers=cashier).status_code == 200
    refreshed = client.get(f"/api/governance/closings?branch_id={ids['cafe_branch']}&business_date={today}", headers=owner).json()
    assert refreshed['status'] == 'open'
    assert Decimal(refreshed['expected_cash']) == Decimal('100') + Decimal(cash)
    assert Decimal(refreshed['non_cash_total']) == Decimal(upi)
    counted = str(Decimal('100') + Decimal(cash) - 5)
    submit = client.post(f"/api/governance/closings/{row['id']}/submit", headers=owner, json={'counted_cash': counted})
    assert submit.status_code == 200, submit.text
    assert submit.json()['variance'] == '-5.00'
    closed = client.post(f"/api/governance/closings/{row['id']}/close", headers=owner)
    assert closed.status_code == 200, closed.text
    cashier = login_headers(client, 'cashier@example.test')
    # A lost successful response remains retrievable after the owner closes the day.
    assert sale(client, cashier, payload(ids), 'v1-close-cash').status_code == 200
    assert sale(client, cashier, payload(ids), 'v1-close-blocked').status_code == 409
    reopened = client.post(f"/api/governance/closings/{row['id']}/reopen", headers=owner, json={'reason': 'Count correction'})
    assert reopened.status_code == 200, reopened.text
    assert sale(client, cashier, payload(ids, quantity=1), 'v1-reopened-sale').status_code == 200


def test_cashier_cannot_access_owner_reports_closing_or_other_venture(client, db_session_factory):
    ids = seed_cashier(db_session_factory)
    cashier = login_headers(client, 'cashier@example.test')
    owner = cafe_headers(client, 'admin')
    for url in ('/api/dashboard/cafe', '/api/exports/cafe', f"/api/governance/closings?branch_id={ids['cafe_branch']}&business_date={business_today()}"):
        assert client.get(url, headers=cashier).status_code == 403
    closing_body = {'branch_id': ids['cafe_branch'], 'business_date': str(business_today()), 'opening_cash': '100'}
    assert client.post('/api/governance/closings', headers=cashier, json=closing_body).status_code == 403
    assert client.post('/api/governance/closings', headers=owner, json={**closing_body, 'branch_id': ids['retail_branch']}).status_code == 404
    assert sale(client, cashier, {**payload(ids), 'branch_id': ids['retail_branch']}).status_code == 403
    assert sale(client, cafe_headers(client, 'analyst'), payload(ids)).status_code == 403
    assert sale(client, cafe_headers(client, 'retail_admin'), payload(ids)).status_code == 403
    assert sale(client, cashier, {**payload(ids, 'upi_mode'), 'reference_number': None}).status_code == 400
    assert client.post('/api/governance/closings', headers=owner, json={**closing_body, 'opening_cash': '-1'}).status_code == 422


def test_collections_follow_payment_date_and_business_midnight(client, db_session_factory):
    from tests.p9_fixtures import seed_p9
    ids = seed_p9(db_session_factory)
    today = business_today()
    start, end = business_bounds(today)
    assert start.hour == 18 and start.minute == 30
    with db_session_factory() as db:
        invoice = db.get(Invoice, ids['cafe_invoice'])
        invoice.invoice_date = start - timedelta(days=1)
        payment = db.scalar(select(InvoicePayment).where(InvoicePayment.invoice_id == invoice.id))
        payment.payment_datetime = start + timedelta(minutes=1)
        db.commit()
    headers = cafe_headers(client, 'admin')
    response = client.get(f'/api/dashboard/cafe?start_date={today}&end_date={today}', headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['kpis']['billed_revenue'] == '0.00'
    assert response.json()['kpis']['collections'] == '40.00'
    assert response.json()['payment_mode_mix']['cash'] == '40.00'
