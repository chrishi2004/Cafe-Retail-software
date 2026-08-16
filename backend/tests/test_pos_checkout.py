from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import CustomerLedgerEntry, Inventory, Invoice, InvoicePayment, Sale, StockMovement
from tests.invoice_test_utils import login, setup_invoice_data


def checkout_payload(ids: dict[str, int], quantity: str = "1.00") -> dict:
    return {
        "branch_id": ids["branch_id"],
        "customer_id": None,
        "invoice_type": "non_gst",
        "place_of_supply_state": "Karnataka",
        "place_of_supply_state_code": "29",
        "invoice_date": "2026-05-21T10:00:00+00:00",
        "items": [{"product_id": ids["product_id"], "quantity": quantity, "discount": "0.00"}],
        "payments": [{"payment_mode_id": ids["cash_mode_id"], "amount": "100.00"}],
    }


def test_pos_product_search_finds_barcode_and_returns_branch_stock(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = setup_invoice_data(client, db_session_factory)
    response = client.get(
        f"/api/pos/products/search?q=8902026999001&branch_id={ids['branch_id']}",
        headers=login(client, email="staff@hybridretail.test"),
    )
    assert response.status_code == 200
    rows = response.json()
    assert rows[0]["product_id"] == ids["product_id"]
    assert rows[0]["sku"] == "POS-SOAP-100"
    assert rows[0]["quantity_on_hand"] == "20.00"
    # Reference tax metadata remains available internally even while billing Non-GST.
    assert rows[0]["gst_rate"] == "18.00"


def test_pos_quote_returns_backend_calculated_totals_without_creating_invoice(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = setup_invoice_data(client, db_session_factory)
    response = client.post(
        "/api/pos/quote",
        json={
            "branch_id": ids["branch_id"],
            "customer_id": None,
            "invoice_type": "non_gst",
            "place_of_supply_state": "Karnataka",
            "place_of_supply_state_code": "29",
            "invoice_date": "2026-05-21T10:00:00+00:00",
            "items": [{"product_id": ids["product_id"], "quantity": "2.00", "discount": "10.00"}],
        },
        headers=login(client, email="staff@hybridretail.test"),
    )

    assert response.status_code == 200
    quote = response.json()
    assert quote["subtotal"] == "200.00"
    assert quote["discount_total"] == "10.00"
    assert quote["taxable_total"] == "190.00"
    assert quote["cgst_total"] == "0.00"
    assert quote["sgst_total"] == "0.00"
    assert quote["igst_total"] == "0.00"
    assert quote["grand_total"] == "190.00"
    assert quote["items"][0]["gst_rate"] == "0.00"
    assert quote["items"][0]["quantity_on_hand"] == "20.00"
    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 0


def test_pos_checkout_creates_invoice_payment_stock_movement_and_sales_compatibility(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = setup_invoice_data(client, db_session_factory)
    response = client.post(
        "/api/pos/checkout",
        json=checkout_payload(ids),
        headers=login(client, email="staff@hybridretail.test"),
    )
    summary_response = client.get(
        f"/api/sales/summary?branch_id={ids['branch_id']}&start_date=2026-05-21&end_date=2026-05-21",
        headers=login(client),
    )

    assert response.status_code == 201
    invoice = response.json()
    assert invoice["status"] == "paid"
    assert invoice["grand_total"] == "100.00"
    assert len(invoice["payments"]) == 1
    assert summary_response.status_code == 200
    assert summary_response.json()["revenue"] == "100.00"
    assert summary_response.json()["tax_total"] == "0.00"
    assert summary_response.json()["transaction_count"] == 1

    with db_session_factory() as db:
        inventory = db.scalar(select(Inventory).where(Inventory.product_id == ids["product_id"], Inventory.branch_id == ids["branch_id"]))
        movement = db.scalar(select(StockMovement).where(StockMovement.reference_type == "invoice"))
        payment = db.scalar(select(InvoicePayment).where(InvoicePayment.invoice_id == invoice["id"]))
        sale = db.get(Sale, invoice["sale_id"])
    assert inventory.quantity_on_hand == Decimal("19.00")
    assert movement is not None
    assert movement.reference_id == invoice["id"]
    assert payment is not None
    assert payment.amount == Decimal("100.00")
    assert sale is not None


def test_pos_checkout_rejects_insufficient_stock_atomically(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = setup_invoice_data(client, db_session_factory, quantity="1.00")
    payload = checkout_payload(ids, quantity="2.00")
    payload["payments"][0]["amount"] = "200.00"
    response = client.post("/api/pos/checkout", json=payload, headers=login(client))

    assert response.status_code == 400
    assert "Insufficient stock" in response.json()["error"]["message"]
    with db_session_factory() as db:
        inventory = db.scalar(select(Inventory).where(Inventory.product_id == ids["product_id"], Inventory.branch_id == ids["branch_id"]))
        invoice_count = db.scalar(select(func.count()).select_from(Invoice))
        movement_count = db.scalar(select(func.count()).select_from(StockMovement))
    assert inventory.quantity_on_hand == Decimal("1.00")
    assert invoice_count == 0
    assert movement_count == 0


def test_pos_credit_checkout_creates_customer_ledger_without_payment_row(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = setup_invoice_data(client, db_session_factory)
    payload = {**checkout_payload(ids), "customer_id": ids["customer_id"], "payments": []}
    response = client.post("/api/pos/checkout", json=payload, headers=login(client, email="staff@hybridretail.test"))

    assert response.status_code == 201
    invoice = response.json()
    assert invoice["status"] == "credit"
    assert invoice["payments"] == []
    with db_session_factory() as db:
        payment_count = db.scalar(select(func.count()).select_from(InvoicePayment))
        ledger_entry = db.scalar(select(CustomerLedgerEntry).where(CustomerLedgerEntry.reference_id == invoice["id"]))
    assert payment_count == 0
    assert ledger_entry is not None
    assert ledger_entry.debit == Decimal("100.00")
