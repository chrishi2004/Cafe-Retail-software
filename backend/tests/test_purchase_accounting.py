from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import PurchaseBill, Supplier, SupplierLedgerEntry
from tests.invoice_test_utils import login, setup_invoice_data


def test_purchase_bill_supplier_ledger_payment_and_debit_note_are_idempotent(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = setup_invoice_data(client, db_session_factory)
    with db_session_factory() as db:
        supplier_id = db.scalar(select(Supplier.id).where(Supplier.name == "POS Supplier"))
    headers = login(client)
    response = client.post("/api/purchase-bills", headers=headers, json={
        "branch_id": ids["branch_id"], "supplier_id": supplier_id, "bill_date": "2026-09-20",
        "supplier_invoice_number": "SUP-100", "idempotency_key": "purchase-bill-test-001",
        "items": [{"product_id": ids["product_id"], "quantity": "2.00", "unit_cost": "60.00"}],
    })
    assert response.status_code == 201, response.text
    bill = response.json()
    assert bill["total_amount"] == "120.00"
    duplicate = client.post("/api/purchase-bills", headers=headers, json={
        "branch_id": ids["branch_id"], "supplier_id": supplier_id, "bill_date": "2026-09-20",
        "idempotency_key": "purchase-bill-test-001", "items": [{"product_id": ids["product_id"], "quantity": "2.00", "unit_cost": "60.00"}],
    })
    assert duplicate.json()["id"] == bill["id"]
    payment = client.post(f"/api/purchase-bills/{bill['id']}/payments", headers=headers, json={"amount": "50.00", "reason": "Bank transfer", "idempotency_key": "supplier-payment-test-001"})
    assert payment.status_code == 200
    assert payment.json()["balance_due"] == "70.00"
    note = client.post(f"/api/purchase-bills/{bill['id']}/debit-notes", headers=headers, json={"amount": "20.00", "reason": "Short shipment", "idempotency_key": "supplier-debit-test-001"})
    assert note.status_code == 200
    assert note.json()["balance_due"] == "50.00"
    ledger = client.get(f"/api/purchase-bills/suppliers/{supplier_id}/ledger", headers=headers)
    assert ledger.status_code == 200
    assert len(ledger.json()) == 3
    with db_session_factory() as db:
        stored = db.get(PurchaseBill, bill["id"])
        entries = db.scalars(select(SupplierLedgerEntry).where(SupplierLedgerEntry.supplier_id == supplier_id)).all()
    assert stored.balance_due == Decimal("50.00")
    assert len(entries) == 3
