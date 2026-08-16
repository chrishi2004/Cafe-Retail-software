from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import CafeOrder, CafeOrderItem, Inventory, Invoice, Sale, StockMovement
from tests.p7_fixtures import cafe_headers, create_public_order, create_staff_dine_in_order, seed_p7


def test_qr_and_staff_orders_share_one_queue_and_server_pricing(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p7(db_session_factory)
    order_taker = cafe_headers(client, "order_taker")

    with db_session_factory() as db:
        inventory_before = db.scalar(
            select(Inventory.quantity_on_hand).where(
                Inventory.company_id == ids["cafe_company"],
                Inventory.branch_id == ids["cafe_branch"],
                Inventory.product_id == ids["cafe_product"],
            )
        )
        invoices_before = db.scalar(select(func.count()).select_from(Invoice))
        sales_before = db.scalar(select(func.count()).select_from(Sale))
        movements_before = db.scalar(select(func.count()).select_from(StockMovement))

    qr = create_public_order(client, ids)
    assert qr.status_code == 201, qr.text
    staff = create_staff_dine_in_order(client, ids, headers=order_taker, quantity=2)
    assert staff.status_code == 201, staff.text
    assert Decimal(staff.json()["subtotal"]) == Decimal("360.00")
    assert Decimal(staff.json()["items"][0]["unit_price"]) == Decimal("180.00")
    assert staff.json()["source_channel"] == "order_taker"
    assert staff.json()["table_session_public_id"] == ids["table_session_public_id"]

    queue = client.get("/api/cafe/orders", headers=order_taker)
    assert queue.status_code == 200, queue.text
    assert {row["source_channel"] for row in queue.json()} == {"qr_customer", "order_taker"}
    assert {row["table_session_public_id"] for row in queue.json()} == {ids["table_session_public_id"]}

    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CafeOrder)) == 2
        assert db.scalar(select(func.count()).select_from(CafeOrderItem)) == 2
        inventory_after = db.scalar(
            select(Inventory.quantity_on_hand).where(
                Inventory.company_id == ids["cafe_company"],
                Inventory.branch_id == ids["cafe_branch"],
                Inventory.product_id == ids["cafe_product"],
            )
        )
        assert inventory_after == inventory_before
        assert db.scalar(select(func.count()).select_from(Invoice)) == invoices_before
        assert db.scalar(select(func.count()).select_from(Sale)) == sales_before
        assert db.scalar(select(func.count()).select_from(StockMovement)) == movements_before


def test_takeaway_and_counter_staff_orders_are_standalone(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p7(db_session_factory)
    headers = cafe_headers(client, "order_taker")
    for order_type, source in (("takeaway", "order_taker"), ("counter", "billing_counter")):
        response = client.post(
            "/api/cafe/orders",
            headers=headers,
            json={
                "order_type": order_type,
                "branch_id": ids["cafe_branch"],
                "items": [{"menu_item_public_id": ids["menu_item_public_id"], "quantity": 1}],
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["table_session_public_id"] is None
        assert response.json()["source_channel"] == source


def test_additional_staff_order_joins_existing_table_session_without_rewriting_prior_order(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p7(db_session_factory)
    headers = cafe_headers(client, "order_taker")
    first = create_staff_dine_in_order(client, ids, headers=headers, quantity=1)
    second = create_staff_dine_in_order(client, ids, headers=headers, quantity=2)
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["public_id"] != second.json()["public_id"]
    assert first.json()["table_session_public_id"] == second.json()["table_session_public_id"]
    assert first.json()["items"][0]["quantity"] == 1
    assert second.json()["items"][0]["quantity"] == 2
