from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Invoice, InvoiceTax
from tests.p7_fixtures import cafe_headers
from tests.p8_fixtures import create_mixed_served_table_orders, seed_p8


def test_non_gst_cafe_bill_has_zero_tax_and_no_gstin_output(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p8(db_session_factory)
    create_mixed_served_table_orders(client, ids)
    headers = cafe_headers(client, "order_taker")
    quote_response = client.get(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/quote", headers=headers
    )
    assert quote_response.status_code == 200, quote_response.text
    quote = quote_response.json()
    for field in ("cgst_total", "sgst_total", "igst_total", "cess_total", "round_off"):
        assert Decimal(quote[field]) == Decimal("0.00")

    billed = client.post(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/bill",
        headers={**headers, "Idempotency-Key": "p8-non-gst-0001"},
        json={
            "expected_version": quote["source_version"],
            "payments": [{"payment_mode_id": ids["cash_mode"], "amount": quote["grand_total"]}],
        },
    )
    assert billed.status_code == 200, billed.text
    receipt = billed.json()["receipt"]
    assert receipt["invoice_type"] == "non_gst"
    assert receipt["gstin"] is None
    for field in ("cgst_total", "sgst_total", "igst_total", "cess_total"):
        assert Decimal(receipt[field]) == Decimal("0.00")
    assert "gstin" in receipt and "customer_gstin" not in receipt

    receipt_api = client.get(
        f"/api/cafe/billing/invoices/{receipt['invoice_id']}/receipt", headers=headers
    )
    assert receipt_api.status_code == 200, receipt_api.text
    assert receipt_api.json()["gstin"] is None

    with db_session_factory() as db:
        invoice = db.get(Invoice, receipt["invoice_id"])
        assert invoice is not None and invoice.invoice_type.value == "non_gst"
        assert invoice.cgst_total == invoice.sgst_total == invoice.igst_total == invoice.cess_total == Decimal("0.00")
        assert db.scalar(
            select(func.count()).select_from(InvoiceTax).where(InvoiceTax.invoice_id == invoice.id)
        ) == 0
