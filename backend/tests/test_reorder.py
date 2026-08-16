from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    AuditLog,
    Branch,
    Category,
    Inventory,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    Sale,
    SaleItem,
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


def add_sale(
    db: Session,
    *,
    sale_number: str,
    branch_id: int,
    created_by: int,
    sale_datetime: datetime,
    product_id: int,
    quantity: Decimal,
    unit_price: Decimal,
) -> None:
    sale = Sale(
        sale_number=sale_number,
        branch_id=branch_id,
        sale_datetime=sale_datetime,
        subtotal=unit_price * quantity,
        discount_total=Decimal("0.00"),
        tax_total=Decimal("0.00"),
        total_amount=unit_price * quantity,
        created_by=created_by,
        created_at=sale_datetime,
    )
    db.add(sale)
    db.flush()
    db.add(
        SaleItem(
            sale_id=sale.id,
            product_id=product_id,
            quantity=quantity,
            unit_price=unit_price,
            discount_amount=Decimal("0.00"),
            line_total=unit_price * quantity,
        )
    )


def seed_reorder_data(db_session_factory: sessionmaker[Session]) -> dict[str, int]:
    with db_session_factory() as db:
        central_branch = db.scalar(select(Branch).where(Branch.name == "Central Market"))
        admin = db.scalar(select(User).where(User.email == "admin@hybridretail.test"))
        manager = db.scalar(select(User).where(User.email == "manager@hybridretail.test"))
        north_branch = Branch(
            name="Northside Express",
            address="88 Ring Road",
            city="Delhi",
            manager_name="Rohan Mehta",
        )
        category = Category(name="Grocery", description="Staples")
        supplier = Supplier(
            name="FreshLine Distributors",
            contact_person="Kavita Shah",
            email="freshline@example.com",
            lead_time_days=3,
        )
        second_supplier = Supplier(
            name="Daily Essentials Co",
            contact_person="Dev Patel",
            email="daily@example.com",
            lead_time_days=5,
        )
        db.add_all([north_branch, category, supplier, second_supplier])
        db.flush()

        critical = Product(
            sku="CRIT-001",
            name="Critical Rice",
            category_id=category.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("10.00"),
            selling_price=Decimal("15.00"),
            reorder_threshold=Decimal("5.00"),
            target_stock_level=Decimal("50.00"),
        )
        high = Product(
            sku="HIGH-001",
            name="High Priority Dal",
            category_id=category.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("20.00"),
            selling_price=Decimal("30.00"),
            reorder_threshold=Decimal("10.00"),
            target_stock_level=Decimal("40.00"),
        )
        medium = Product(
            sku="MED-001",
            name="Medium Priority Oil",
            category_id=category.id,
            supplier_id=second_supplier.id,
            unit_cost=Decimal("30.00"),
            selling_price=Decimal("45.00"),
            reorder_threshold=Decimal("10.00"),
            target_stock_level=Decimal("40.00"),
        )
        healthy = Product(
            sku="LOW-001",
            name="Healthy Salt",
            category_id=category.id,
            supplier_id=second_supplier.id,
            unit_cost=Decimal("5.00"),
            selling_price=Decimal("8.00"),
            reorder_threshold=Decimal("10.00"),
            target_stock_level=Decimal("40.00"),
        )
        db.add_all([critical, high, medium, healthy])
        db.flush()

        db.add_all(
            [
                Inventory(
                    product_id=critical.id,
                    branch_id=central_branch.id,
                    quantity_on_hand=Decimal("0.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("2.00"),
                ),
                Inventory(
                    product_id=high.id,
                    branch_id=central_branch.id,
                    quantity_on_hand=Decimal("4.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("0.00"),
                ),
                Inventory(
                    product_id=medium.id,
                    branch_id=central_branch.id,
                    quantity_on_hand=Decimal("12.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("0.00"),
                ),
                Inventory(
                    product_id=healthy.id,
                    branch_id=central_branch.id,
                    quantity_on_hand=Decimal("45.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("0.00"),
                ),
                Inventory(
                    product_id=critical.id,
                    branch_id=north_branch.id,
                    quantity_on_hand=Decimal("0.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("0.00"),
                ),
            ]
        )

        for day, quantity in [(16, Decimal("2.00")), (17, Decimal("2.00")), (18, Decimal("2.00"))]:
            add_sale(
                db,
                sale_number=f"SAL-CRIT-{day}",
                branch_id=central_branch.id,
                created_by=manager.id,
                sale_datetime=datetime(2026, 5, day, 10, 0, tzinfo=UTC),
                product_id=critical.id,
                quantity=quantity,
                unit_price=Decimal("15.00"),
            )

        db.commit()
        return {
            "central_branch_id": central_branch.id,
            "north_branch_id": north_branch.id,
            "category_id": category.id,
            "supplier_id": supplier.id,
            "second_supplier_id": second_supplier.id,
            "critical_id": critical.id,
            "high_id": high.id,
            "medium_id": medium.id,
            "healthy_id": healthy.id,
        }


def test_reorder_recommendations_calculate_velocity_priority_and_quantity(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_reorder_data(db_session_factory)

    response = client.get(
        (
            "/api/inventory/reorder-recommendations"
            f"?branch_id={ids['central_branch_id']}&lookback_days=3&as_of_date=2026-05-18"
        ),
        headers=login(client),
    )

    assert response.status_code == 200
    rows = response.json()
    by_product = {row["product_id"]: row for row in rows}
    assert [row["priority"] for row in rows[:3]] == ["critical", "high", "medium"]

    critical = by_product[ids["critical_id"]]
    assert critical["current_stock"] == "0.00"
    assert critical["quantity_on_order"] == "2.00"
    assert critical["average_daily_sales"] == "2.00"
    assert critical["supplier_lead_time_days"] == 3
    assert critical["expected_demand_during_lead_time"] == "6.00"
    assert critical["days_until_stockout"] == "0.00"
    assert critical["suggested_reorder_quantity"] == "56.00"
    assert critical["estimated_cost"] == "560.00"

    assert by_product[ids["high_id"]]["priority"] == "high"
    assert by_product[ids["medium_id"]]["priority"] == "medium"
    assert by_product[ids["healthy_id"]]["priority"] == "low"
    assert all(Decimal(row["suggested_reorder_quantity"]) >= 0 for row in rows)


def test_reorder_recommendations_filter_by_priority_and_enforce_branch_scope(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_reorder_data(db_session_factory)
    manager_headers = login(client, email="manager@hybridretail.test")

    filtered_response = client.get(
        "/api/inventory/reorder-recommendations?priority=critical&lookback_days=3&as_of_date=2026-05-18",
        headers=manager_headers,
    )
    forbidden_response = client.get(
        f"/api/inventory/reorder-recommendations?branch_id={ids['north_branch_id']}",
        headers=manager_headers,
    )

    assert filtered_response.status_code == 200
    assert {row["priority"] for row in filtered_response.json()} == {"critical"}
    assert {row["branch_id"] for row in filtered_response.json()} == {ids["central_branch_id"]}
    assert forbidden_response.status_code == 403


def test_create_purchase_order_draft_from_recommendations_groups_by_supplier_and_branch(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_reorder_data(db_session_factory)
    response = client.post(
        "/api/purchase-orders/from-recommendations",
        json={
            "items": [
                {
                    "product_id": ids["critical_id"],
                    "branch_id": ids["central_branch_id"],
                    "quantity_ordered": "56.00",
                },
                {
                    "product_id": ids["high_id"],
                    "branch_id": ids["central_branch_id"],
                    "quantity_ordered": "36.00",
                },
                {
                    "product_id": ids["medium_id"],
                    "branch_id": ids["central_branch_id"],
                    "quantity_ordered": "28.00",
                },
            ]
        },
        headers=login(client),
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    first_order = next(order for order in payload if order["supplier_id"] == ids["supplier_id"])
    second_order = next(order for order in payload if order["supplier_id"] == ids["second_supplier_id"])
    assert first_order["status"] == "draft"
    assert first_order["branch_id"] == ids["central_branch_id"]
    assert first_order["total_amount"] == "1280.00"
    assert {item["product_id"] for item in first_order["items"]} == {ids["critical_id"], ids["high_id"]}
    assert second_order["total_amount"] == "840.00"
    assert second_order["items"][0]["quantity_ordered"] == "28.00"

    with db_session_factory() as db:
        orders = db.scalars(select(PurchaseOrder)).all()
        items = db.scalars(select(PurchaseOrderItem)).all()
        audit_logs = db.scalars(
            select(AuditLog).where(AuditLog.action == "purchase_orders.create_from_recommendations")
        ).all()
        inventory = db.scalar(
            select(Inventory).where(
                Inventory.product_id == ids["critical_id"],
                Inventory.branch_id == ids["central_branch_id"],
            )
        )

    assert len(orders) == 2
    assert len(items) == 3
    assert len(audit_logs) == 2
    assert inventory.quantity_on_hand == Decimal("0.00")
    assert inventory.quantity_on_order == Decimal("2.00")


def test_read_only_users_cannot_create_purchase_order_drafts(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_reorder_data(db_session_factory)
    response = client.post(
        "/api/purchase-orders/from-recommendations",
        json={
            "items": [
                {
                    "product_id": ids["critical_id"],
                    "branch_id": ids["central_branch_id"],
                    "quantity_ordered": "10.00",
                }
            ]
        },
        headers=login(client, email="analyst@hybridretail.test"),
    )

    assert response.status_code == 403
