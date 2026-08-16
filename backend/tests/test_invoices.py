from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import CustomerLedgerEntry, Inventory, Invoice, InvoicePayment, Sale, StockMovement, StockMovementType
from tests.invoice_test_utils import login, setup_invoice_data


def draft_invoice_payload(ids: dict[str, int]) -> dict:
    return {
        "branch_id": ids["branch_id"],
        "customer_id": None,
        "invoice_type": "non_gst",
        "place_of_supply_state": "Karnataka",
        "place_of_supply_state_code": "29",
        "invoice_date": "2026-05-21T10:00:00+00:00",
        "items": [{"product_id": ids["product_id"], "quantity": "2.00", "discount": "0.00"}],
    }


def test_draft_invoice_does_not_reduce_stock_and_issue_reduces_stock(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = setup_invoice_data(client, db_session_factory)
    staff_headers = login(client, email="staff@hybridretail.test")

    draft_response = client.post("/api/invoices", json=draft_invoice_payload(ids), headers=staff_headers)
    assert draft_response.status_code == 201, draft_response.text
    invoice_id = draft_response.json()["id"]

    assert draft_response.json()["status"] == "draft"
    assert draft_response.json()["sale_id"] is None
    assert draft_response.json()["grand_total"] == "200.00"
    with db_session_factory() as db:
        inventory = db.scalar(select(Inventory).where(Inventory.product_id == ids["product_id"], Inventory.branch_id == ids["branch_id"]))
        movement_count = db.scalar(select(func.count()).select_from(StockMovement))
    assert inventory.quantity_on_hand == Decimal("20.00")
    assert movement_count == 0

    issue_response = client.post(
        f"/api/invoices/{invoice_id}/issue",
        json={"payments": [{"payment_mode_id": ids["cash_mode_id"], "amount": "200.00"}]},
        headers=staff_headers,
    )

    assert issue_response.status_code == 200
    issued = issue_response.json()
    assert issued["status"] == "paid"
    assert issued["payment_status"] == "paid"
    assert issued["paid_amount"] == "200.00"
    assert issued["balance_due"] == "0.00"
    assert issued["sale_id"] is not None
    with db_session_factory() as db:
        inventory = db.scalar(select(Inventory).where(Inventory.product_id == ids["product_id"], Inventory.branch_id == ids["branch_id"]))
        movement = db.scalar(select(StockMovement).where(StockMovement.reference_type == "invoice"))
        sale = db.get(Sale, issued["sale_id"])
    assert inventory.quantity_on_hand == Decimal("18.00")
    assert movement is not None
    assert movement.movement_type == StockMovementType.SALE
    assert movement.quantity_change == Decimal("-2.00")
    assert sale is not None
    assert sale.total_amount == Decimal("200.00")


def test_credit_invoice_creates_customer_receivable_ledger(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = setup_invoice_data(client, db_session_factory)
    response = client.post(
        "/api/pos/checkout",
        json={
            **draft_invoice_payload(ids),
            "customer_id": ids["customer_id"],
            "items": [{"product_id": ids["product_id"], "quantity": "1.00", "discount": "0.00"}],
            "payments": [],
        },
        headers=login(client, email="staff@hybridretail.test"),
    )

    assert response.status_code == 201
    invoice = response.json()
    assert invoice["status"] == "credit"
    assert invoice["paid_amount"] == "0.00"
    assert invoice["balance_due"] == "100.00"
    with db_session_factory() as db:
        ledger_entry = db.scalar(
            select(CustomerLedgerEntry).where(
                CustomerLedgerEntry.customer_id == ids["customer_id"],
                CustomerLedgerEntry.reference_type == "invoice",
                CustomerLedgerEntry.reference_id == invoice["id"],
            )
        )
    assert ledger_entry is not None
    assert ledger_entry.debit == Decimal("100.00")
    assert ledger_entry.credit == Decimal("0.00")


def test_invoice_payment_collection_updates_balance_and_customer_ledger(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = setup_invoice_data(client, db_session_factory)
    headers = login(client)
    invoice_response = client.post(
        "/api/pos/checkout",
        json={
            **draft_invoice_payload(ids),
            "customer_id": ids["customer_id"],
            "items": [{"product_id": ids["product_id"], "quantity": "1.00", "discount": "0.00"}],
            "payments": [],
        },
        headers=headers,
    )
    assert invoice_response.status_code == 201, invoice_response.text
    invoice = invoice_response.json()

    payment_response = client.post(
        f"/api/invoices/{invoice['id']}/payments",
        json={"payment_mode_id": ids["cash_mode_id"], "amount": "50.00", "reference_number": "RCPT-INV-1"},
        headers=headers,
    )

    assert payment_response.status_code == 200
    updated = payment_response.json()
    assert updated["status"] == "partial_paid"
    assert updated["paid_amount"] == "50.00"
    assert updated["balance_due"] == "50.00"
    with db_session_factory() as db:
        payment = db.scalar(select(InvoicePayment).where(InvoicePayment.invoice_id == invoice["id"]))
        payment_ledger = db.scalar(select(CustomerLedgerEntry).where(CustomerLedgerEntry.customer_id == ids["customer_id"], CustomerLedgerEntry.entry_type == "payment"))
    assert payment is not None
    assert payment.amount == Decimal("50.00")
    assert payment_ledger is not None
    assert payment_ledger.credit == Decimal("50.00")


def test_invoice_number_is_unique_across_checkouts(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = setup_invoice_data(client, db_session_factory)
    headers = login(client)
    checkout_payload = {
        **draft_invoice_payload(ids),
        "items": [{"product_id": ids["product_id"], "quantity": "1.00", "discount": "0.00"}],
        "payments": [{"payment_mode_id": ids["cash_mode_id"], "amount": "100.00"}],
    }

    first = client.post("/api/pos/checkout", json=checkout_payload, headers=headers)
    second = client.post("/api/pos/checkout", json=checkout_payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["invoice_number"] == "BILL-2026-0001"
    assert second.json()["invoice_number"] == "BILL-2026-0002"
    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 2


def test_analyst_cannot_create_invoice(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = setup_invoice_data(client, db_session_factory)
    response = client.post(
        "/api/invoices",
        json=draft_invoice_payload(ids),
        headers=login(client, email="analyst@hybridretail.test"),
    )
    assert response.status_code == 403
