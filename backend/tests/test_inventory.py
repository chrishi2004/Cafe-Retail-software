from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    AuditLog,
    Branch,
    Category,
    Inventory,
    Product,
    StockMovement,
    Supplier,
)


def login(client, email: str = "admin@hybridretail.test") -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "RetailDemo@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_inventory_data(db_session_factory: sessionmaker[Session]) -> dict[str, int]:
    with db_session_factory() as db:
        central_branch = db.scalar(select(Branch).where(Branch.name == "Central Market"))
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
        db.add_all([north_branch, category, supplier])
        db.flush()
        rice = Product(
            sku="RICE-5KG",
            name="Rice Premium 5kg",
            category_id=category.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("360.00"),
            selling_price=Decimal("485.00"),
            reorder_threshold=Decimal("40.00"),
            target_stock_level=Decimal("180.00"),
        )
        water = Product(
            sku="WATER-1L",
            name="Mineral Water 1L",
            category_id=category.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("12.00"),
            selling_price=Decimal("20.00"),
            reorder_threshold=Decimal("75.00"),
            target_stock_level=Decimal("280.00"),
        )
        db.add_all([rice, water])
        db.flush()
        db.add_all(
            [
                Inventory(
                    product_id=rice.id,
                    branch_id=central_branch.id,
                    quantity_on_hand=Decimal("50.00"),
                    quantity_reserved=Decimal("2.00"),
                    quantity_on_order=Decimal("10.00"),
                ),
                Inventory(
                    product_id=water.id,
                    branch_id=central_branch.id,
                    quantity_on_hand=Decimal("20.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("80.00"),
                ),
                Inventory(
                    product_id=rice.id,
                    branch_id=north_branch.id,
                    quantity_on_hand=Decimal("90.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("0.00"),
                ),
            ]
        )
        db.commit()
        return {
            "central_branch_id": central_branch.id,
            "north_branch_id": north_branch.id,
            "category_id": category.id,
            "supplier_id": supplier.id,
            "rice_id": rice.id,
            "water_id": water.id,
        }


def test_inventory_list_shows_real_values_and_stock_value(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_inventory_data(db_session_factory)
    response = client.get("/api/inventory", headers=login(client))

    assert response.status_code == 200
    payload = response.json()
    rice_central = next(
        row
        for row in payload
        if row["product_id"] == ids["rice_id"] and row["branch_id"] == ids["central_branch_id"]
    )
    assert rice_central["product_sku"] == "RICE-5KG"
    assert rice_central["category_name"] == "Grocery"
    assert rice_central["supplier_name"] == "FreshLine Distributors"
    assert rice_central["quantity_on_hand"] == "50.00"
    assert rice_central["stock_value"] == "18000.00"
    assert rice_central["is_low_stock"] is False


def test_low_stock_filter_works(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_inventory_data(db_session_factory)

    response = client.get("/api/inventory?low_stock=true", headers=login(client))

    assert response.status_code == 200
    assert [row["product_id"] for row in response.json()] == [ids["water_id"]]


def test_manager_inventory_is_scoped_to_assigned_branch(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_inventory_data(db_session_factory)
    headers = login(client, email="manager@hybridretail.test")

    scoped_response = client.get("/api/inventory", headers=headers)
    forbidden_response = client.get(
        f"/api/inventory?branch_id={ids['north_branch_id']}",
        headers=headers,
    )

    assert scoped_response.status_code == 200
    assert {row["branch_id"] for row in scoped_response.json()} == {ids["central_branch_id"]}
    assert forbidden_response.status_code == 403


def test_manual_adjustment_changes_inventory_and_writes_movement_and_audit(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_inventory_data(db_session_factory)

    response = client.post(
        "/api/inventory/adjustments",
        json={
            "product_id": ids["rice_id"],
            "branch_id": ids["central_branch_id"],
            "quantity_change": "7.00",
            "reason": "Cycle count correction",
        },
        headers=login(client),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["inventory"]["quantity_on_hand"] == "57.00"
    assert payload["movement"]["movement_type"] == "manual_adjustment"
    assert payload["movement"]["quantity_change"] == "7.00"

    with db_session_factory() as db:
        inventory = db.scalar(
            select(Inventory).where(
                Inventory.product_id == ids["rice_id"],
                Inventory.branch_id == ids["central_branch_id"],
            )
        )
        movement_count = db.scalar(select(StockMovement).where(StockMovement.product_id == ids["rice_id"]))
        audit = db.scalar(select(AuditLog).where(AuditLog.action == "inventory.adjust"))

    assert inventory.quantity_on_hand == Decimal("57.00")
    assert movement_count is not None
    assert audit is not None
    assert audit.entity_type == "inventory"


def test_adjustment_cannot_make_stock_negative(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_inventory_data(db_session_factory)

    response = client.post(
        "/api/inventory/adjustments",
        json={
            "product_id": ids["rice_id"],
            "branch_id": ids["central_branch_id"],
            "quantity_change": "-999.00",
            "reason": "Bad correction",
        },
        headers=login(client),
    )

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Adjustment would make quantity on hand negative."


def test_read_only_and_unconfigured_staff_roles_cannot_adjust_stock(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_inventory_data(db_session_factory)
    payload = {
        "product_id": ids["rice_id"],
        "branch_id": ids["central_branch_id"],
        "quantity_change": "1.00",
        "reason": "Role test",
    }

    analyst_response = client.post(
        "/api/inventory/adjustments",
        json=payload,
        headers=login(client, email="analyst@hybridretail.test"),
    )
    staff_response = client.post(
        "/api/inventory/adjustments",
        json=payload,
        headers=login(client, email="staff@hybridretail.test"),
    )

    assert analyst_response.status_code == 403
    assert staff_response.status_code == 403


def test_stock_movement_list_returns_adjustment(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_inventory_data(db_session_factory)
    headers = login(client)
    client.post(
        "/api/inventory/adjustments",
        json={
            "product_id": ids["rice_id"],
            "branch_id": ids["central_branch_id"],
            "quantity_change": "2.00",
            "reason": "Movement list test",
        },
        headers=headers,
    )

    response = client.get(f"/api/inventory/movements?product_id={ids['rice_id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["reason"] == "Movement list test"


def test_product_inventory_detail_returns_accessible_branches(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_inventory_data(db_session_factory)

    response = client.get(f"/api/inventory/{ids['rice_id']}", headers=login(client))

    assert response.status_code == 200
    payload = response.json()
    assert payload["product_sku"] == "RICE-5KG"
    assert payload["total_quantity_on_hand"] == "140.00"
    assert len(payload["inventory"]) == 2
