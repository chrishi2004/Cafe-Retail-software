from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    Branch,
    Category,
    Inventory,
    Product,
    PurchaseOrder,
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


def add_sale(
    db: Session,
    *,
    sale_number: str,
    branch_id: int,
    created_by: int,
    sale_datetime: datetime,
    items: list[tuple[int, Decimal, Decimal, Decimal]],
) -> Sale:
    subtotal = sum((line_total for _product_id, _quantity, _unit_price, line_total in items), Decimal("0.00"))
    sale = Sale(
        sale_number=sale_number,
        branch_id=branch_id,
        sale_datetime=sale_datetime,
        subtotal=subtotal,
        discount_total=Decimal("0.00"),
        tax_total=Decimal("0.00"),
        total_amount=subtotal,
        created_by=created_by,
        created_at=sale_datetime,
    )
    db.add(sale)
    db.flush()
    for product_id, quantity, unit_price, line_total in items:
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
    return sale


def seed_dashboard_data(db_session_factory: sessionmaker[Session]) -> dict[str, int]:
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
            sale_number="SAL-CURRENT-1",
            branch_id=central_branch.id,
            created_by=manager.id,
            sale_datetime=datetime(2026, 5, 18, 10, 15, tzinfo=UTC),
            items=[
                (rice.id, Decimal("2.00"), Decimal("15.00"), Decimal("30.00")),
                (water.id, Decimal("3.00"), Decimal("8.00"), Decimal("24.00")),
            ],
        )
        add_sale(
            db,
            sale_number="SAL-CURRENT-2",
            branch_id=central_branch.id,
            created_by=manager.id,
            sale_datetime=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
            items=[(rice.id, Decimal("1.00"), Decimal("15.00"), Decimal("15.00"))],
        )
        add_sale(
            db,
            sale_number="SAL-PREVIOUS-1",
            branch_id=central_branch.id,
            created_by=manager.id,
            sale_datetime=datetime(2026, 5, 16, 12, 0, tzinfo=UTC),
            items=[(water.id, Decimal("2.00"), Decimal("8.00"), Decimal("16.00"))],
        )
        add_sale(
            db,
            sale_number="SAL-NORTH-1",
            branch_id=north_branch.id,
            created_by=admin.id,
            sale_datetime=datetime(2026, 5, 18, 12, 0, tzinfo=UTC),
            items=[(rice.id, Decimal("10.00"), Decimal("15.00"), Decimal("150.00"))],
        )

        db.add_all(
            [
                PurchaseOrder(
                    po_number="PO-CENTRAL-PENDING",
                    supplier_id=supplier.id,
                    branch_id=central_branch.id,
                    status=PurchaseOrderStatus.PENDING_APPROVAL,
                    order_date=date(2026, 5, 18),
                    expected_delivery_date=date(2026, 5, 21),
                    total_amount=Decimal("100.00"),
                    created_by=admin.id,
                ),
                PurchaseOrder(
                    po_number="PO-CENTRAL-APPROVED",
                    supplier_id=supplier.id,
                    branch_id=central_branch.id,
                    status=PurchaseOrderStatus.APPROVED,
                    order_date=date(2026, 5, 17),
                    expected_delivery_date=date(2026, 5, 19),
                    total_amount=Decimal("50.00"),
                    created_by=admin.id,
                ),
                PurchaseOrder(
                    po_number="PO-NORTH-PENDING",
                    supplier_id=supplier.id,
                    branch_id=north_branch.id,
                    status=PurchaseOrderStatus.PENDING_APPROVAL,
                    order_date=date(2026, 5, 18),
                    expected_delivery_date=date(2026, 5, 21),
                    total_amount=Decimal("200.00"),
                    created_by=admin.id,
                ),
            ]
        )
        db.commit()
        return {
            "central_branch_id": central_branch.id,
            "north_branch_id": north_branch.id,
            "category_id": category.id,
            "rice_id": rice.id,
        }


def test_overview_dashboard_returns_real_kpis_and_chart_data(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_dashboard_data(db_session_factory)
    response = client.get(
        "/api/dashboard/overview?start_date=2026-05-17&end_date=2026-05-18",
        headers=login(client),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["kpis"]["sales"]["revenue"] == "219.00"
    assert payload["kpis"]["sales"]["previous_period_revenue"] == "16.00"
    assert payload["kpis"]["sales"]["sales_growth_percent"] == "1268.75"
    assert payload["kpis"]["sales"]["gross_profit"] == "74.00"
    assert payload["kpis"]["sales"]["units_sold"] == "16.00"
    assert payload["kpis"]["sales"]["transaction_count"] == 3
    assert payload["kpis"]["inventory"]["current_stock_value"] == "310.00"
    assert payload["kpis"]["inventory"]["low_stock_product_count"] == 1
    assert payload["kpis"]["purchase_orders"]["pending_purchase_orders"] == 3
    assert payload["kpis"]["top_selling_product"]["product_id"] == ids["rice_id"]
    assert len(payload["sales_trend"]) == 2
    assert payload["revenue_by_category"][0]["category_name"] == "Grocery"
    assert payload["branch_performance"][0]["branch_name"] == "Northside Express"
    assert payload["low_stock_items"][0]["product_sku"] == "RICE-5KG"


def test_sales_dashboard_filters_by_branch_and_category(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_dashboard_data(db_session_factory)
    response = client.get(
        (
            "/api/dashboard/sales?start_date=2026-05-17&end_date=2026-05-18"
            f"&branch_id={ids['central_branch_id']}&category_id={ids['category_id']}"
        ),
        headers=login(client),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["revenue"] == "69.00"
    assert payload["summary"]["gross_profit"] == "24.00"
    assert payload["summary"]["sales_growth_percent"] == "331.25"
    assert len(payload["top_products"]) == 2
    assert payload["branch_performance"] == [
        {
            "branch_id": ids["central_branch_id"],
            "branch_name": "Central Market",
            "revenue": "69.00",
            "gross_profit": "24.00",
            "units_sold": "6.00",
            "transaction_count": 2,
        }
    ]


def test_inventory_dashboard_detects_low_and_slow_moving_stock(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_dashboard_data(db_session_factory)
    response = client.get(
        f"/api/dashboard/inventory?start_date=2026-05-17&end_date=2026-05-18&branch_id={ids['central_branch_id']}",
        headers=login(client),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["current_stock_value"] == "130.00"
    assert payload["summary"]["low_stock_product_count"] == 1
    assert payload["inventory_health"][0]["status"] in {"Healthy", "Low stock"}
    assert payload["low_stock_items"][0]["product_sku"] == "RICE-5KG"
    assert payload["slow_moving_stock"] == []


def test_dashboard_enforces_branch_scope_for_store_manager(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_dashboard_data(db_session_factory)
    manager_headers = login(client, email="manager@hybridretail.test")

    response = client.get(
        "/api/dashboard/sales?start_date=2026-05-17&end_date=2026-05-18",
        headers=manager_headers,
    )
    forbidden_response = client.get(
        f"/api/dashboard/sales?start_date=2026-05-17&end_date=2026-05-18&branch_id={ids['north_branch_id']}",
        headers=manager_headers,
    )

    assert response.status_code == 200
    assert response.json()["summary"]["revenue"] == "69.00"
    assert forbidden_response.status_code == 403
