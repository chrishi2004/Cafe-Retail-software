from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Customer, CustomerLedgerEntry, Invoice, InvoicePayment, TableSession, TableSessionStatus
from tests.p7_fixtures import cafe_headers
from tests.p8_fixtures import create_mixed_served_table_orders, seed_p8


def test_split_cash_upi_payment_reconciles_and_closes(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p8(db_session_factory)
    create_mixed_served_table_orders(client, ids)
    headers = cafe_headers(client, "order_taker")
    quote = client.get(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/quote", headers=headers
    ).json()
    billed = client.post(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/bill",
        headers={**headers, "Idempotency-Key": "p8-split-pay-0001"},
        json={
            "expected_version": quote["source_version"],
            "payments": [
                {"payment_mode_id": ids["cash_mode"], "amount": "180.00"},
                {
                    "payment_mode_id": ids["upi_mode"],
                    "amount": "180.00",
                    "reference_number": "UPI-P8-001",
                },
            ],
        },
    )
    assert billed.status_code == 200, billed.text
    receipt = billed.json()["receipt"]
    assert receipt["payment_status"] == "paid"
    assert receipt["paid_amount"] == "360.00"
    assert receipt["balance_due"] == "0.00"
    assert len(receipt["payments"]) == 2
    with db_session_factory() as db:
        invoice = db.get(Invoice, receipt["invoice_id"])
        assert invoice is not None
        assert db.scalar(select(func.count()).select_from(InvoicePayment).where(InvoicePayment.invoice_id == invoice.id)) == 2


def test_required_payment_reference_and_anonymous_partial_balance_fail_closed(
    client, db_session_factory: sessionmaker[Session]
):
    ids = seed_p8(db_session_factory)
    create_mixed_served_table_orders(client, ids)
    headers = cafe_headers(client, "order_taker")
    quote = client.get(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/quote", headers=headers
    ).json()

    missing_ref = client.post(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/bill",
        headers={**headers, "Idempotency-Key": "p8-missing-ref-0001"},
        json={
            "expected_version": quote["source_version"],
            "payments": [{"payment_mode_id": ids["upi_mode"], "amount": quote["grand_total"]}],
        },
    )
    assert missing_ref.status_code == 400

    partial = client.post(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/bill",
        headers={**headers, "Idempotency-Key": "p8-partial-anon-0002"},
        json={
            "expected_version": quote["source_version"],
            "payments": [{"payment_mode_id": ids["cash_mode"], "amount": "100.00"}],
        },
    )
    assert partial.status_code == 400
    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Invoice).where(Invoice.company_id == ids["cafe_company"])) == 0


def test_customer_credit_bill_stays_billed_until_collection_then_closes(
    client, db_session_factory: sessionmaker[Session]
):
    ids = seed_p8(db_session_factory)
    with db_session_factory() as db:
        customer = Customer(
            company_id=ids["cafe_company"],
            branch_id=ids["cafe_branch"],
            name="Cafe Credit Customer",
            phone="9000000001",
            credit_limit=Decimal("1000.00"),
            opening_balance=Decimal("0.00"),
            is_active=True,
        )
        db.add(customer)
        db.commit()
        ids["customer"] = customer.id

    create_mixed_served_table_orders(client, ids)
    headers = cafe_headers(client, "order_taker")
    quote = client.get(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/quote", headers=headers
    ).json()
    credit_bill = client.post(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/bill",
        headers={**headers, "Idempotency-Key": "p8-credit-bill-0001"},
        json={"expected_version": quote["source_version"], "customer_id": ids["customer"], "payments": []},
    )
    assert credit_bill.status_code == 200, credit_bill.text
    body = credit_bill.json()
    assert body["closed"] is False
    assert body["table_session_status"] == "billed"
    assert body["receipt"]["payment_status"] == "credit"
    assert body["receipt"]["balance_due"] == "360.00"
    invoice_id = body["receipt"]["invoice_id"]

    collected = client.post(
        f"/api/cafe/billing/invoices/{invoice_id}/payments",
        headers=headers,
        json={"payment": {"payment_mode_id": ids["cash_mode"], "amount": "360.00"}},
    )
    assert collected.status_code == 200, collected.text
    assert collected.json()["closed"] is True
    assert collected.json()["receipt"]["balance_due"] == "0.00"
    assert collected.json()["receipt"]["payment_status"] == "paid"

    with db_session_factory() as db:
        session = db.get(TableSession, ids["table_session"])
        assert session is not None and session.status == TableSessionStatus.CLOSED
        entries = list(
            db.scalars(select(CustomerLedgerEntry).where(CustomerLedgerEntry.customer_id == ids["customer"])).all()
        )
        assert sum((row.debit for row in entries), Decimal("0")) == Decimal("360.00")
        assert sum((row.credit for row in entries), Decimal("0")) == Decimal("360.00")


def test_kitchen_analyst_and_retail_cannot_use_cafe_billing(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p8(db_session_factory)
    create_mixed_served_table_orders(client, ids)
    url = f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/quote"
    assert client.get(url, headers=cafe_headers(client, "kitchen")).status_code == 403
    assert client.get(url, headers=cafe_headers(client, "analyst")).status_code == 403
    assert client.get(url, headers=cafe_headers(client, "retail_admin")).status_code == 403
