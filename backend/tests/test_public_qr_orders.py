from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    CafeOrder,
    CafeOrderItem,
    CafeOrderStatusHistory,
    Inventory,
    Invoice,
    Sale,
    StockMovement,
    TableSession,
    TableSessionStatus,
)
from tests.p6_fixtures import seed_p6_public_ordering


def _open_guest(client: TestClient, ids: dict[str, object]) -> tuple[str, str]:
    response = client.post(f"/api/public/cafe/qr/{ids['raw_qr']}/resolve")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ordering_enabled"] is True
    assert "company_id" not in body and "branch_id" not in body
    return body["session_public_id"], body["guest_access"]


def test_public_qr_customer_can_view_menu_place_order_and_request_bill(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p6_public_ordering(db_session_factory)
    session_public_id, guest_access = _open_guest(client, ids)
    headers = {"X-Guest-Access": guest_access}

    menu = client.get(f"/api/public/cafe/sessions/{session_public_id}/menu", headers=headers)
    assert menu.status_code == 200, menu.text
    menu_body = menu.json()
    assert menu_body["items"][0]["public_id"] == ids["menu_item_public_id"]
    assert menu_body["items"][0]["public_id"] != str(ids["menu_item"])
    assert "company_id" not in menu.text
    assert "branch_id" not in menu.text
    assert "product_id" not in menu.text
    assert "stock" not in menu.text.lower()

    with db_session_factory() as db:
        inventory_before = db.scalar(
            select(Inventory.quantity_on_hand).where(
                Inventory.company_id == ids["cafe_company"],
                Inventory.branch_id == ids["cafe_branch"],
                Inventory.product_id == ids["cafe_product"],
            )
        )
        invoice_before = db.scalar(select(func.count()).select_from(Invoice))
        sale_before = db.scalar(select(func.count()).select_from(Sale))
        movement_before = db.scalar(select(func.count()).select_from(StockMovement))

    order = client.post(
        f"/api/public/cafe/sessions/{session_public_id}/orders",
        headers={**headers, "Idempotency-Key": "p6-first-order-0001"},
        json={
            "items": [
                {
                    "menu_item_public_id": ids["menu_item_public_id"],
                    "quantity": 2,
                    "notes": "<script>alert('x')</script>",
                }
            ],
            "customer_notes": "Please serve together <b>thanks</b>",
        },
    )
    assert order.status_code == 201, order.text
    order_body = order.json()
    assert order_body["status"] == "placed"
    assert Decimal(order_body["subtotal"]) == Decimal("360.00")
    assert Decimal(order_body["estimated_total"]) == Decimal("360.00")
    assert order_body["items"][0]["unit_price"] == "180.00"
    assert order_body["items"][0]["notes"] == "<script>alert('x')</script>"
    assert "company_id" not in order.text and "branch_id" not in order.text
    assert "menu_item_id" not in order.text and "created_by" not in order.text

    listed = client.get(f"/api/public/cafe/sessions/{session_public_id}/orders", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["orders"]) == 1
    assert listed.json()["orders"][0]["public_id"] == order_body["public_id"]

    bill = client.post(f"/api/public/cafe/sessions/{session_public_id}/bill-request", headers=headers)
    assert bill.status_code == 200, bill.text
    assert bill.json()["session_status"] == "bill_requested"

    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CafeOrder)) == 1
        assert db.scalar(select(func.count()).select_from(CafeOrderItem)) == 1
        assert db.scalar(select(func.count()).select_from(CafeOrderStatusHistory)) == 1
        inventory_after = db.scalar(
            select(Inventory.quantity_on_hand).where(
                Inventory.company_id == ids["cafe_company"],
                Inventory.branch_id == ids["cafe_branch"],
                Inventory.product_id == ids["cafe_product"],
            )
        )
        assert inventory_after == inventory_before
        assert db.scalar(select(func.count()).select_from(Invoice)) == invoice_before
        assert db.scalar(select(func.count()).select_from(Sale)) == sale_before
        assert db.scalar(select(func.count()).select_from(StockMovement)) == movement_before
        table_session = db.get(TableSession, ids["table_session"])
        assert table_session is not None
        assert table_session.status == TableSessionStatus.BILL_REQUESTED
        assert table_session.bill_requested_at is not None


def test_server_ignores_client_price_by_rejecting_price_fields(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p6_public_ordering(db_session_factory)
    session_public_id, guest_access = _open_guest(client, ids)
    response = client.post(
        f"/api/public/cafe/sessions/{session_public_id}/orders",
        headers={"X-Guest-Access": guest_access, "Idempotency-Key": "p6-tamper-price-0001"},
        json={
            "items": [{"menu_item_public_id": ids["menu_item_public_id"], "quantity": 1, "unit_price": "1.00"}],
            "status": "billed",
            "company_id": 1,
        },
    )
    assert response.status_code == 422
    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CafeOrder)) == 0
