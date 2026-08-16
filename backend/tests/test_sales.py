from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    AuditLog,
    Branch,
    Category,
    Inventory,
    Product,
    Sale,
    StockMovement,
    StockMovementType,
    Supplier,
)


def login(client, email: str = "admin@hybridretail.test") -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "RetailDemo@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_sales_data(db_session_factory: sessionmaker[Session]) -> dict[str, int]:
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
            unit_cost=Decimal("10.00"),
            selling_price=Decimal("15.00"),
            reorder_threshold=Decimal("5.00"),
            target_stock_level=Decimal("50.00"),
        )
        water = Product(
            sku="WATER-1L",
            name="Mineral Water 1L",
            category_id=category.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("5.00"),
            selling_price=Decimal("8.00"),
            reorder_threshold=Decimal("5.00"),
            target_stock_level=Decimal("50.00"),
        )
        db.add_all([rice, water])
        db.flush()

        db.add_all(
            [
                Inventory(
                    product_id=rice.id,
                    branch_id=central_branch.id,
                    quantity_on_hand=Decimal("20.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("0.00"),
                ),
                Inventory(
                    product_id=water.id,
                    branch_id=central_branch.id,
                    quantity_on_hand=Decimal("10.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("0.00"),
                ),
                Inventory(
                    product_id=rice.id,
                    branch_id=north_branch.id,
                    quantity_on_hand=Decimal("15.00"),
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


def sale_payload(ids: dict[str, int], branch_id_key: str = "central_branch_id") -> dict[str, object]:
    return {
        "branch_id": ids[branch_id_key],
        "sale_datetime": "2026-05-18T10:15:00+00:00",
        "tax_rate": "0.05",
        "items": [
            {
                "product_id": ids["rice_id"],
                "quantity": "2.00",
                "discount_amount": "1.00",
            },
            {
                "product_id": ids["water_id"],
                "quantity": "3.00",
                "discount_amount": "0.00",
            },
        ],
    }


def test_staff_can_create_sale_with_multiple_items_and_inventory_movements(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_sales_data(db_session_factory)

    response = client.post(
        "/api/sales",
        json=sale_payload(ids),
        headers=login(client, email="staff@hybridretail.test"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["branch_id"] == ids["central_branch_id"]
    assert payload["subtotal"] == "53.00"
    assert payload["discount_total"] == "1.00"
    assert payload["tax_total"] == "2.65"
    assert payload["total_amount"] == "55.65"
    assert payload["gross_profit"] == "18.00"
    assert payload["units_sold"] == "5.00"
    assert len(payload["items"]) == 2

    sale_id = payload["id"]
    with db_session_factory() as db:
        rice_inventory = db.scalar(
            select(Inventory).where(
                Inventory.product_id == ids["rice_id"],
                Inventory.branch_id == ids["central_branch_id"],
            )
        )
        water_inventory = db.scalar(
            select(Inventory).where(
                Inventory.product_id == ids["water_id"],
                Inventory.branch_id == ids["central_branch_id"],
            )
        )
        movements = db.scalars(
            select(StockMovement)
            .where(StockMovement.reference_type == "sale", StockMovement.reference_id == sale_id)
            .order_by(StockMovement.product_id)
        ).all()
        audit = db.scalar(select(AuditLog).where(AuditLog.action == "sales.create"))

    assert rice_inventory.quantity_on_hand == Decimal("18.00")
    assert water_inventory.quantity_on_hand == Decimal("7.00")
    assert [movement.movement_type for movement in movements] == [
        StockMovementType.SALE,
        StockMovementType.SALE,
    ]
    assert [movement.quantity_change for movement in movements] == [Decimal("-2.00"), Decimal("-3.00")]
    assert audit is not None
    assert audit.entity_type == "sale"
    assert audit.entity_id == sale_id


def test_sale_detail_and_sales_list_return_created_sale(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_sales_data(db_session_factory)
    headers = login(client)
    created = client.post("/api/sales", json=sale_payload(ids), headers=headers).json()

    list_response = client.get("/api/sales?limit=10", headers=headers)
    detail_response = client.get(f"/api/sales/{created['id']}", headers=headers)

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == created["id"]
    assert list_response.json()[0]["gross_profit"] == "18.00"
    assert detail_response.status_code == 200
    assert detail_response.json()["sale_number"] == created["sale_number"]
    assert len(detail_response.json()["items"]) == 2


def test_insufficient_stock_rejects_sale_and_keeps_inventory_unchanged(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_sales_data(db_session_factory)
    payload = sale_payload(ids)
    payload["items"] = [
        {
            "product_id": ids["rice_id"],
            "quantity": "999.00",
            "discount_amount": "0.00",
        }
    ]

    response = client.post("/api/sales", json=payload, headers=login(client))

    assert response.status_code == 400
    assert "Insufficient stock" in response.json()["error"]["message"]
    with db_session_factory() as db:
        sale_count = db.scalar(select(func.count()).select_from(Sale))
        inventory = db.scalar(
            select(Inventory).where(
                Inventory.product_id == ids["rice_id"],
                Inventory.branch_id == ids["central_branch_id"],
            )
        )
        movement_count = db.scalar(select(func.count()).select_from(StockMovement))

    assert sale_count == 0
    assert inventory.quantity_on_hand == Decimal("20.00")
    assert movement_count == 0


def test_analyst_cannot_create_sale(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_sales_data(db_session_factory)

    response = client.post(
        "/api/sales",
        json=sale_payload(ids),
        headers=login(client, email="analyst@hybridretail.test"),
    )

    assert response.status_code == 403


def test_manager_cannot_create_sale_for_other_branch(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_sales_data(db_session_factory)
    payload = {
        "branch_id": ids["north_branch_id"],
        "sale_datetime": "2026-05-18T10:15:00+00:00",
        "tax_rate": "0.05",
        "items": [
            {
                "product_id": ids["rice_id"],
                "quantity": "1.00",
                "discount_amount": "0.00",
            }
        ],
    }

    response = client.post(
        "/api/sales",
        json=payload,
        headers=login(client, email="manager@hybridretail.test"),
    )

    assert response.status_code == 403


def test_sales_summary_and_trends_return_business_metrics(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_sales_data(db_session_factory)
    headers = login(client)
    client.post("/api/sales", json=sale_payload(ids), headers=headers)

    summary_response = client.get(
        f"/api/sales/summary?branch_id={ids['central_branch_id']}&start_date=2026-05-18&end_date=2026-05-18",
        headers=headers,
    )
    trend_response = client.get(
        f"/api/sales/trends?branch_id={ids['central_branch_id']}&start_date=2026-05-18&end_date=2026-05-18",
        headers=headers,
    )

    assert summary_response.status_code == 200
    assert summary_response.json() == {
        "revenue": "53.00",
        "gross_profit": "18.00",
        "units_sold": "5.00",
        "transaction_count": 1,
        "average_order_value": "53.00",
        "discount_total": "1.00",
        "tax_total": "2.65",
    }
    assert trend_response.status_code == 200
    assert trend_response.json() == [
        {
            "date": "2026-05-18",
            "revenue": "53.00",
            "gross_profit": "18.00",
            "units_sold": "5.00",
            "transaction_count": 1,
        }
    ]
