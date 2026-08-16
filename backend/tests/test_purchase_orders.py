from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    AuditLog,
    Branch,
    Category,
    Inventory,
    Product,
    PurchaseOrder,
    PurchaseOrderStatus,
    StockMovement,
    StockMovementType,
    Supplier,
    User,
)


def login(client, email: str = "admin@hybridretail.test") -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "RetailDemo@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_purchase_order_data(db_session_factory: sessionmaker[Session]) -> dict[str, int]:
    with db_session_factory() as db:
        branch = db.scalar(select(Branch).where(Branch.name == "Central Market"))
        category = Category(name="Grocery", description="Staples")
        supplier = Supplier(
            name="FreshLine Distributors",
            contact_person="Kavita Shah",
            email="freshline@example.com",
            lead_time_days=4,
        )
        db.add_all([category, supplier])
        db.flush()

        rice = Product(
            sku="PO-RIC-001",
            name="Purchase Rice",
            category_id=category.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("10.00"),
            selling_price=Decimal("15.00"),
            reorder_threshold=Decimal("5.00"),
            target_stock_level=Decimal("50.00"),
        )
        dal = Product(
            sku="PO-DAL-001",
            name="Purchase Dal",
            category_id=category.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("20.00"),
            selling_price=Decimal("30.00"),
            reorder_threshold=Decimal("5.00"),
            target_stock_level=Decimal("50.00"),
        )
        db.add_all([rice, dal])
        db.flush()

        db.add_all(
            [
                Inventory(
                    product_id=rice.id,
                    branch_id=branch.id,
                    quantity_on_hand=Decimal("10.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("0.00"),
                ),
                Inventory(
                    product_id=dal.id,
                    branch_id=branch.id,
                    quantity_on_hand=Decimal("5.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("0.00"),
                ),
            ]
        )
        db.commit()
        return {
            "branch_id": branch.id,
            "supplier_id": supplier.id,
            "rice_id": rice.id,
            "dal_id": dal.id,
        }


def create_purchase_order(client, ids: dict[str, int], headers: dict[str, str], quantity: str = "8.00") -> dict:
    response = client.post(
        "/api/purchase-orders",
        json={
            "supplier_id": ids["supplier_id"],
            "branch_id": ids["branch_id"],
            "order_date": "2026-05-18",
            "expected_delivery_date": "2026-05-22",
            "items": [
                {
                    "product_id": ids["rice_id"],
                    "quantity_ordered": quantity,
                }
            ],
        },
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def test_purchase_order_lifecycle_receiving_updates_inventory_and_ledger(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_purchase_order_data(db_session_factory)
    headers = login(client)

    created = create_purchase_order(client, ids, headers)
    order_id = created["id"]
    item_id = created["items"][0]["id"]

    assert created["status"] == "draft"
    assert created["total_amount"] == "80.00"

    submitted = client.post(f"/api/purchase-orders/{order_id}/submit", headers=headers)
    approved = client.post(f"/api/purchase-orders/{order_id}/approve", headers=headers)
    ordered = client.post(f"/api/purchase-orders/{order_id}/mark-ordered", headers=headers)
    partial = client.post(
        f"/api/purchase-orders/{order_id}/receive",
        json={"items": [{"item_id": item_id, "quantity_received": "3.00"}]},
        headers=headers,
    )
    received = client.post(
        f"/api/purchase-orders/{order_id}/receive",
        json={"items": [{"item_id": item_id, "quantity_received": "5.00"}]},
        headers=headers,
    )

    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_approval"
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by_name"] == "Admin User"
    assert ordered.status_code == 200
    assert ordered.json()["status"] == "ordered"
    assert partial.status_code == 200
    assert partial.json()["status"] == "partially_received"
    assert partial.json()["items"][0]["quantity_received"] == "3.00"
    assert partial.json()["items"][0]["remaining_quantity"] == "5.00"
    assert received.status_code == 200
    assert received.json()["status"] == "received"
    assert received.json()["items"][0]["quantity_received"] == "8.00"

    with db_session_factory() as db:
        inventory = db.scalar(
            select(Inventory).where(
                Inventory.product_id == ids["rice_id"],
                Inventory.branch_id == ids["branch_id"],
            )
        )
        movements = db.scalars(
            select(StockMovement)
            .where(
                StockMovement.reference_type == "purchase_order",
                StockMovement.reference_id == order_id,
            )
            .order_by(StockMovement.id)
        ).all()
        audit_actions = [
            log.action
            for log in db.scalars(
                select(AuditLog)
                .where(AuditLog.entity_type == "purchase_order", AuditLog.entity_id == order_id)
                .order_by(AuditLog.id)
            ).all()
        ]

    assert inventory.quantity_on_hand == Decimal("18.00")
    assert inventory.quantity_on_order == Decimal("0.00")
    assert [movement.movement_type for movement in movements] == [
        StockMovementType.PURCHASE_RECEIVED,
        StockMovementType.PURCHASE_RECEIVED,
    ]
    assert [movement.quantity_change for movement in movements] == [Decimal("3.00"), Decimal("5.00")]
    assert audit_actions == [
        "purchase_orders.create",
        "purchase_orders.submit",
        "purchase_orders.approve",
        "purchase_orders.mark_ordered",
        "purchase_orders.receive",
        "purchase_orders.receive",
    ]


def test_purchase_order_invalid_transitions_and_unauthorized_approval_are_rejected(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_purchase_order_data(db_session_factory)
    admin_headers = login(client)
    manager_headers = login(client, email="manager@hybridretail.test")
    analyst_headers = login(client, email="analyst@hybridretail.test")
    created = create_purchase_order(client, ids, admin_headers)
    order_id = created["id"]

    premature_ordered = client.post(f"/api/purchase-orders/{order_id}/mark-ordered", headers=admin_headers)
    update_after_submit = None
    submit_response = client.post(f"/api/purchase-orders/{order_id}/submit", headers=admin_headers)
    manager_approve = client.post(f"/api/purchase-orders/{order_id}/approve", headers=manager_headers)
    analyst_cancel = client.post(f"/api/purchase-orders/{order_id}/cancel", headers=analyst_headers)
    update_after_submit = client.put(
        f"/api/purchase-orders/{order_id}",
        json={
            "supplier_id": ids["supplier_id"],
            "branch_id": ids["branch_id"],
            "items": [
                {
                    "product_id": ids["rice_id"],
                    "quantity_ordered": "10.00",
                }
            ],
        },
        headers=admin_headers,
    )

    assert premature_ordered.status_code == 400
    assert submit_response.status_code == 200
    assert manager_approve.status_code == 403
    assert analyst_cancel.status_code == 403
    assert update_after_submit.status_code == 400


def test_draft_update_recalculates_totals_and_list_filters_work(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_purchase_order_data(db_session_factory)
    headers = login(client)
    created = create_purchase_order(client, ids, headers)

    update_response = client.put(
        f"/api/purchase-orders/{created['id']}",
        json={
            "supplier_id": ids["supplier_id"],
            "branch_id": ids["branch_id"],
            "order_date": "2026-05-18",
            "expected_delivery_date": "2026-05-23",
            "items": [
                {
                    "product_id": ids["rice_id"],
                    "quantity_ordered": "5.00",
                    "unit_cost": "11.00",
                },
                {
                    "product_id": ids["dal_id"],
                    "quantity_ordered": "2.00",
                },
            ],
        },
        headers=headers,
    )
    list_response = client.get("/api/purchase-orders?status=draft&search=FreshLine", headers=headers)

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["total_amount"] == "95.00"
    assert payload["item_count"] == 2
    assert payload["total_quantity_ordered"] == "7.00"
    assert list_response.status_code == 200
    assert any(row["id"] == created["id"] for row in list_response.json())


def test_cancel_order_reduces_quantity_on_order_without_changing_quantity_on_hand(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_purchase_order_data(db_session_factory)
    headers = login(client)
    created = create_purchase_order(client, ids, headers, quantity="6.00")
    order_id = created["id"]

    client.post(f"/api/purchase-orders/{order_id}/submit", headers=headers)
    client.post(f"/api/purchase-orders/{order_id}/approve", headers=headers)
    client.post(f"/api/purchase-orders/{order_id}/mark-ordered", headers=headers)
    cancel_response = client.post(f"/api/purchase-orders/{order_id}/cancel", headers=headers)

    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    with db_session_factory() as db:
        inventory = db.scalar(
            select(Inventory).where(
                Inventory.product_id == ids["rice_id"],
                Inventory.branch_id == ids["branch_id"],
            )
        )
        movement_count = db.scalar(
            select(func.count())
            .select_from(StockMovement)
            .where(StockMovement.reference_type == "purchase_order", StockMovement.reference_id == order_id)
        )
        purchase_order = db.get(PurchaseOrder, order_id)

    assert inventory.quantity_on_hand == Decimal("10.00")
    assert inventory.quantity_on_order == Decimal("0.00")
    assert purchase_order.status == PurchaseOrderStatus.CANCELLED
    assert movement_count == 0
