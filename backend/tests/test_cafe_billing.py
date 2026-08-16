from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import CafeOrder, CafeOrderItem, Invoice, InvoiceItem, Sale, TableSession, TableSessionStatus
from tests.p7_fixtures import cafe_headers
from tests.p8_fixtures import advance_order_to_served, create_mixed_served_table_orders, seed_p8


def test_qr_and_staff_orders_bill_once_and_release_table(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p8(db_session_factory)
    create_mixed_served_table_orders(client, ids)
    headers = cafe_headers(client, "order_taker")

    quote = client.get(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/quote",
        headers=headers,
    )
    assert quote.status_code == 200, quote.text
    q = quote.json()
    assert len(q["eligible_items"]) == 2
    assert Decimal(q["grand_total"]) == Decimal("360.00")

    billed = client.post(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/bill",
        headers={**headers, "Idempotency-Key": "p8-table-bill-0001"},
        json={
            "expected_version": q["source_version"],
            "payments": [{"payment_mode_id": ids["cash_mode"], "amount": "360.00"}],
        },
    )
    assert billed.status_code == 200, billed.text
    body = billed.json()
    assert body["closed"] is True
    assert body["table_session_status"] == "closed"
    assert body["receipt"]["source_type"] == "cafe_table_session"
    assert body["receipt"]["grand_total"] == "360.00"
    assert body["receipt"]["balance_due"] == "0.00"

    with db_session_factory() as db:
        invoices = list(db.scalars(select(Invoice).where(Invoice.company_id == ids["cafe_company"])).all())
        assert len(invoices) == 1
        invoice = invoices[0]
        assert invoice.source_id == ids["table_session_public_id"]
        assert db.scalar(select(func.count()).select_from(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id)) == 2
        assert db.scalar(select(func.count()).select_from(Sale).where(Sale.company_id == ids["cafe_company"])) == 1
        assert db.scalar(
            select(func.count()).select_from(CafeOrder).where(CafeOrder.billed_invoice_id == invoice.id)
        ) == 2
        assert db.scalar(
            select(func.count()).select_from(CafeOrderItem).where(CafeOrderItem.billed_invoice_item_id.is_not(None))
        ) == 2
        session = db.get(TableSession, ids["table_session"])
        assert session is not None
        assert session.status == TableSessionStatus.CLOSED
        assert session.billed_invoice_id == invoice.id

    reopened = client.post(
        "/api/cafe/table-sessions",
        headers=cafe_headers(client, "admin"),
        json={"table_id": ids["table"], "session_type": "dine_in"},
    )
    assert reopened.status_code == 201, reopened.text
    assert reopened.json()["status"] == "open"


def test_takeaway_order_uses_same_invoice_engine(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p8(db_session_factory)
    headers = cafe_headers(client, "order_taker")
    created = client.post(
        "/api/cafe/orders",
        headers=headers,
        json={
            "order_type": "takeaway",
            "branch_id": ids["cafe_branch"],
            "items": [{"menu_item_public_id": ids["menu_item_public_id"], "quantity": 1}],
        },
    )
    assert created.status_code == 201, created.text
    served = advance_order_to_served(client, headers, created.json()["public_id"])
    quote = client.get(f"/api/cafe/billing/orders/{served['public_id']}/quote", headers=headers)
    assert quote.status_code == 200, quote.text
    q = quote.json()
    billed = client.post(
        f"/api/cafe/billing/orders/{served['public_id']}/bill",
        headers={**headers, "Idempotency-Key": "p8-takeaway-0001"},
        json={
            "expected_version": q["source_version"],
            "payments": [{"payment_mode_id": ids["cash_mode"], "amount": q["grand_total"]}],
        },
    )
    assert billed.status_code == 200, billed.text
    assert billed.json()["closed"] is True
    assert billed.json()["receipt"]["source_type"] == "cafe_takeaway"
