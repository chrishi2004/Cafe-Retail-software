from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import CafeOrder, CafeOrderItem, Inventory, Invoice, InvoiceItem, SaleItem, StockMovement
from tests.p7_fixtures import cafe_headers
from tests.p8_fixtures import (
    create_mixed_served_table_orders,
    create_unlinked_served_order,
    seed_p8,
)


def _inventory(db: Session, ids: dict[str, object]) -> Decimal:
    value = db.scalar(
        select(Inventory.quantity_on_hand).where(
            Inventory.company_id == ids["cafe_company"],
            Inventory.branch_id == ids["cafe_branch"],
            Inventory.product_id == ids["cafe_product"],
        )
    )
    assert value is not None
    return value


def test_linked_stock_reduces_once_with_matching_movements(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p8(db_session_factory)
    create_mixed_served_table_orders(client, ids)
    headers = cafe_headers(client, "order_taker")
    with db_session_factory() as db:
        before = _inventory(db, ids)

    quote = client.get(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/quote", headers=headers
    ).json()
    billed = client.post(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/bill",
        headers={**headers, "Idempotency-Key": "p8-stock-once-0001"},
        json={
            "expected_version": quote["source_version"],
            "payments": [{"payment_mode_id": ids["cash_mode"], "amount": quote["grand_total"]}],
        },
    )
    assert billed.status_code == 200, billed.text

    replay = client.post(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/bill",
        headers={**headers, "Idempotency-Key": "p8-stock-once-0001"},
        json={
            "expected_version": quote["source_version"],
            "payments": [{"payment_mode_id": ids["cash_mode"], "amount": quote["grand_total"]}],
        },
    )
    assert replay.status_code == 200

    with db_session_factory() as db:
        assert _inventory(db, ids) == before - Decimal("2.00")
        movements = list(
            db.scalars(
                select(StockMovement).where(
                    StockMovement.company_id == ids["cafe_company"],
                    StockMovement.reference_type == "invoice",
                )
            ).all()
        )
        assert len(movements) == 2
        assert sum((row.quantity_change for row in movements), Decimal("0")) == Decimal("-2.00")


def test_unlinked_prepared_food_has_no_fake_stock_effect(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p8(db_session_factory)
    create_unlinked_served_order(client, ids)
    headers = cafe_headers(client, "order_taker")
    with db_session_factory() as db:
        stock_before = _inventory(db, ids)
        movement_before = db.scalar(select(func.count()).select_from(StockMovement))

    quote = client.get(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/quote", headers=headers
    ).json()
    assert quote["eligible_items"][0]["product_id"] is None
    billed = client.post(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/bill",
        headers={**headers, "Idempotency-Key": "p8-unlinked-food-0001"},
        json={
            "expected_version": quote["source_version"],
            "payments": [{"payment_mode_id": ids["cash_mode"], "amount": quote["grand_total"]}],
        },
    )
    assert billed.status_code == 200, billed.text
    invoice_id = billed.json()["receipt"]["invoice_id"]

    with db_session_factory() as db:
        assert _inventory(db, ids) == stock_before
        assert db.scalar(select(func.count()).select_from(StockMovement)) == movement_before
        invoice_item = db.scalar(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id))
        assert invoice_item is not None and invoice_item.product_id is None
        sale_item = db.scalar(select(SaleItem).join(Invoice, Invoice.sale_id == SaleItem.sale_id).where(Invoice.id == invoice_id))
        assert sale_item is not None and sale_item.product_id is None


def test_failure_mid_checkout_rolls_back_invoice_links_and_stock(
    client,
    db_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
):
    ids = seed_p8(db_session_factory)
    create_mixed_served_table_orders(client, ids)
    headers = cafe_headers(client, "order_taker")
    quote = client.get(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/quote", headers=headers
    ).json()
    with db_session_factory() as db:
        stock_before = _inventory(db, ids)

    def fail_after_invoice(*_args, **_kwargs):
        raise RuntimeError("simulated payment/stock boundary failure")

    monkeypatch.setattr("app.services.cafe_billing.add_invoice_payments", fail_after_invoice)
    with pytest.raises(RuntimeError, match="simulated"):
        client.post(
            f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/bill",
            headers={**headers, "Idempotency-Key": "p8-rollback-0001"},
            json={
                "expected_version": quote["source_version"],
                "payments": [{"payment_mode_id": ids["cash_mode"], "amount": quote["grand_total"]}],
            },
        )

    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Invoice).where(Invoice.company_id == ids["cafe_company"])) == 0
        assert db.scalar(
            select(func.count()).select_from(StockMovement).where(StockMovement.company_id == ids["cafe_company"])
        ) == 0
        assert _inventory(db, ids) == stock_before
        assert db.scalar(
            select(func.count()).select_from(CafeOrder).where(CafeOrder.billed_invoice_id.is_not(None))
        ) == 0
        assert db.scalar(
            select(func.count()).select_from(CafeOrderItem).where(CafeOrderItem.billed_invoice_item_id.is_not(None))
        ) == 0
