import csv
from datetime import UTC, date, datetime
from decimal import Decimal
from io import StringIO

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    Branch,
    Category,
    Forecast,
    ForecastType,
    Inventory,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
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


def csv_rows(response) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(response.text)))


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
    line_total = quantity * unit_price
    sale = Sale(
        sale_number=sale_number,
        branch_id=branch_id,
        sale_datetime=sale_datetime,
        subtotal=line_total,
        discount_total=Decimal("0.00"),
        tax_total=Decimal("0.00"),
        total_amount=line_total,
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
            line_total=line_total,
        )
    )


def seed_export_data(db_session_factory: sessionmaker[Session]) -> dict[str, int]:
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
        db.add_all([north_branch, category, supplier])
        db.flush()

        rice = Product(
            sku="EXPORT-RICE-5KG",
            name="Export Rice 5kg",
            category_id=category.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("10.00"),
            selling_price=Decimal("15.00"),
            reorder_threshold=Decimal("5.00"),
            target_stock_level=Decimal("50.00"),
        )
        water = Product(
            sku="EXPORT-WATER-1L",
            name="Export Water 1L",
            category_id=category.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("5.00"),
            selling_price=Decimal("8.00"),
            reorder_threshold=Decimal("8.00"),
            target_stock_level=Decimal("80.00"),
        )
        db.add_all([rice, water])
        db.flush()

        db.add_all(
            [
                Inventory(
                    product_id=rice.id,
                    branch_id=central_branch.id,
                    quantity_on_hand=Decimal("3.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("12.00"),
                ),
                Inventory(
                    product_id=water.id,
                    branch_id=central_branch.id,
                    quantity_on_hand=Decimal("20.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("0.00"),
                ),
                Inventory(
                    product_id=rice.id,
                    branch_id=north_branch.id,
                    quantity_on_hand=Decimal("18.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("0.00"),
                ),
            ]
        )

        add_sale(
            db,
            sale_number="EXP-CENTRAL-1",
            branch_id=central_branch.id,
            created_by=manager.id,
            sale_datetime=datetime(2026, 5, 18, 10, 15, tzinfo=UTC),
            product_id=rice.id,
            quantity=Decimal("2.00"),
            unit_price=Decimal("15.00"),
        )
        add_sale(
            db,
            sale_number="EXP-NORTH-1",
            branch_id=north_branch.id,
            created_by=admin.id,
            sale_datetime=datetime(2026, 5, 18, 12, 0, tzinfo=UTC),
            product_id=water.id,
            quantity=Decimal("4.00"),
            unit_price=Decimal("8.00"),
        )

        central_po = PurchaseOrder(
            po_number="PO-EXPORT-CENTRAL",
            supplier_id=supplier.id,
            branch_id=central_branch.id,
            status=PurchaseOrderStatus.ORDERED,
            order_date=date(2026, 5, 18),
            expected_delivery_date=date(2026, 5, 21),
            total_amount=Decimal("100.00"),
            created_by=admin.id,
        )
        north_po = PurchaseOrder(
            po_number="PO-EXPORT-NORTH",
            supplier_id=supplier.id,
            branch_id=north_branch.id,
            status=PurchaseOrderStatus.PENDING_APPROVAL,
            order_date=date(2026, 5, 18),
            expected_delivery_date=date(2026, 5, 21),
            total_amount=Decimal("60.00"),
            created_by=admin.id,
        )
        db.add_all([central_po, north_po])
        db.flush()
        db.add_all(
            [
                PurchaseOrderItem(
                    purchase_order_id=central_po.id,
                    product_id=rice.id,
                    quantity_ordered=Decimal("10.00"),
                    quantity_received=Decimal("2.00"),
                    unit_cost=Decimal("10.00"),
                    line_total=Decimal("100.00"),
                ),
                PurchaseOrderItem(
                    purchase_order_id=north_po.id,
                    product_id=water.id,
                    quantity_ordered=Decimal("12.00"),
                    quantity_received=Decimal("0.00"),
                    unit_cost=Decimal("5.00"),
                    line_total=Decimal("60.00"),
                ),
                Forecast(
                    branch_id=central_branch.id,
                    product_id=rice.id,
                    forecast_type=ForecastType.DEMAND,
                    forecast_start_date=date(2026, 5, 19),
                    forecast_end_date=date(2026, 5, 25),
                    forecast_value=Decimal("21.00"),
                    confidence_low=Decimal("18.00"),
                    confidence_high=Decimal("24.00"),
                    model_name="test_model",
                ),
                Forecast(
                    branch_id=north_branch.id,
                    product_id=water.id,
                    forecast_type=ForecastType.UNITS,
                    forecast_start_date=date(2026, 5, 19),
                    forecast_end_date=date(2026, 5, 25),
                    forecast_value=Decimal("14.00"),
                    confidence_low=Decimal("12.00"),
                    confidence_high=Decimal("16.00"),
                    model_name="test_model",
                ),
            ]
        )
        db.commit()

        return {
            "central_branch_id": central_branch.id,
            "north_branch_id": north_branch.id,
            "supplier_id": supplier.id,
        }


def test_admin_can_export_sales_csv_with_clear_headers(client, db_session_factory: sessionmaker[Session]) -> None:
    seed_export_data(db_session_factory)
    response = client.get(
        "/api/exports/sales?start_date=2026-05-18&end_date=2026-05-18",
        headers=login(client),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "sales_export.csv" in response.headers["content-disposition"]
    rows = csv_rows(response)
    assert set(rows[0]) == {
        "sale_number",
        "sale_datetime",
        "branch_name",
        "product_sku",
        "product_name",
        "category_name",
        "quantity",
        "unit_price",
        "discount_amount",
        "line_total",
        "gross_profit",
        "created_by_name",
    }
    assert {row["branch_name"] for row in rows} == {"Central Market", "Northside Express"}
    assert {row["sale_number"] for row in rows} == {"EXP-CENTRAL-1", "EXP-NORTH-1"}


def test_exports_respect_branch_scope_and_reporting_roles(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_export_data(db_session_factory)
    manager_headers = login(client, email="manager@hybridretail.test")
    staff_headers = login(client, email="staff@hybridretail.test")

    manager_response = client.get("/api/exports/sales", headers=manager_headers)
    forbidden_branch_response = client.get(
        f"/api/exports/sales?branch_id={ids['north_branch_id']}",
        headers=manager_headers,
    )
    staff_response = client.get("/api/exports/sales", headers=staff_headers)

    assert manager_response.status_code == 200
    assert {row["branch_name"] for row in csv_rows(manager_response)} == {"Central Market"}
    assert forbidden_branch_response.status_code == 403
    assert staff_response.status_code == 403


def test_inventory_purchase_order_and_forecast_exports(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_export_data(db_session_factory)
    headers = login(client)

    inventory_response = client.get("/api/exports/inventory?low_stock=true", headers=headers)
    purchase_order_response = client.get(
        f"/api/exports/purchase-orders?status=ordered&supplier_id={ids['supplier_id']}",
        headers=headers,
    )
    forecast_response = client.get("/api/exports/forecasts?forecast_type=demand", headers=headers)

    assert inventory_response.status_code == 200
    inventory_rows = csv_rows(inventory_response)
    assert {row["product_sku"] for row in inventory_rows} == {"EXPORT-RICE-5KG"}
    assert inventory_rows[0]["is_low_stock"] == "true"

    assert purchase_order_response.status_code == 200
    purchase_order_rows = csv_rows(purchase_order_response)
    assert purchase_order_rows[0]["po_number"] == "PO-EXPORT-CENTRAL"
    assert purchase_order_rows[0]["remaining_quantity"] == "8.00"

    assert forecast_response.status_code == 200
    forecast_rows = csv_rows(forecast_response)
    assert forecast_rows[0]["forecast_type"] == "demand"
    assert forecast_rows[0]["scope_type"] == "product"
    assert forecast_rows[0]["branch_name"] == "Central Market"
