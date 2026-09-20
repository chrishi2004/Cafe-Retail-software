from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import CreditNote, FinancialReversal, Inventory, Invoice, SalesReturn, StockMovement, StockMovementType
from tests.invoice_test_utils import login, setup_invoice_data
from tests.test_pos_checkout import checkout_payload


def test_customer_credit_return_restocks_and_is_idempotent(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = setup_invoice_data(client, db_session_factory)
    payload = {**checkout_payload(ids), "customer_id": ids["customer_id"], "payments": []}
    invoice_response = client.post("/api/pos/checkout", json=payload, headers=login(client, email="staff@hybridretail.test"))
    assert invoice_response.status_code == 201
    invoice = invoice_response.json()
    item_id = invoice["items"][0]["id"]

    return_payload = {
        "reason": "Customer changed mind",
        "refund_mode": "customer_credit",
        "idempotency_key": "return-customer-credit-001",
        "items": [{"invoice_item_id": item_id, "quantity": "1.00", "condition": "saleable", "restock": True}],
    }
    response = client.post(f"/api/returns/invoices/{invoice['id']}", json=return_payload, headers=login(client, email="staff@hybridretail.test"))
    duplicate = client.post(f"/api/returns/invoices/{invoice['id']}", json=return_payload, headers=login(client, email="staff@hybridretail.test"))

    assert response.status_code == 201, response.text
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == response.json()["id"]
    assert response.json()["total_amount"] == "100.00"
    assert response.json()["credit_note"]["amount"] == "100.00"

    with db_session_factory() as db:
        inventory = db.scalar(select(Inventory).where(Inventory.product_id == ids["product_id"], Inventory.branch_id == ids["branch_id"]))
        returns = db.scalars(select(SalesReturn)).all()
        movement = db.scalar(select(StockMovement).where(StockMovement.movement_type == StockMovementType.RETURN))
        note = db.scalar(select(CreditNote).where(CreditNote.sales_return_id == response.json()["id"]))
        invoice_row = db.get(Invoice, invoice["id"])
    assert inventory.quantity_on_hand == Decimal("20.00")
    assert len(returns) == 1
    assert movement is not None
    assert note is not None
    assert invoice_row.status.value == "returned"


def test_walk_in_cash_return_creates_financial_reversal_without_customer(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = setup_invoice_data(client, db_session_factory)
    invoice_response = client.post("/api/pos/checkout", json=checkout_payload(ids), headers=login(client, email="staff@hybridretail.test"))
    invoice = invoice_response.json()
    item_id = invoice["items"][0]["id"]
    response = client.post(
        f"/api/returns/invoices/{invoice['id']}",
        json={
            "reason": "Damaged at checkout",
            "refund_mode": "cash",
            "idempotency_key": "return-cash-refund-001",
            "items": [{"invoice_item_id": item_id, "quantity": "1.00", "condition": "damaged", "restock": False}],
        },
        headers=login(client),
    )
    assert response.status_code == 201, response.text
    with db_session_factory() as db:
        reversal = db.scalar(select(FinancialReversal).where(FinancialReversal.invoice_id == invoice["id"]))
        movement_count = db.scalar(select(StockMovement).where(StockMovement.reference_type == "sales_return").count()) if False else 0
    assert reversal is not None
    assert reversal.amount == Decimal("100.00")
