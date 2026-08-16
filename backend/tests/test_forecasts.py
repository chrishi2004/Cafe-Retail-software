from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    Branch,
    Category,
    Forecast,
    ForecastType,
    Product,
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


def seed_forecast_data(db_session_factory: sessionmaker[Session]) -> dict[str, int]:
    with db_session_factory() as db:
        central_branch = db.scalar(select(Branch).where(Branch.name == "Central Market"))
        manager = db.scalar(select(User).where(User.email == "manager@hybridretail.test"))
        admin = db.scalar(select(User).where(User.email == "admin@hybridretail.test"))
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
            lead_time_days=4,
        )
        db.add_all([north_branch, category, supplier])
        db.flush()

        rice = Product(
            sku="FRC-RIC-001",
            name="Forecast Rice",
            category_id=category.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("10.00"),
            selling_price=Decimal("20.00"),
            reorder_threshold=Decimal("5.00"),
            target_stock_level=Decimal("50.00"),
        )
        sparse = Product(
            sku="FRC-SPR-001",
            name="Sparse Forecast Product",
            category_id=category.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("5.00"),
            selling_price=Decimal("8.00"),
            reorder_threshold=Decimal("5.00"),
            target_stock_level=Decimal("30.00"),
        )
        db.add_all([rice, sparse])
        db.flush()

        start_date = datetime(2026, 3, 22, 10, 0, tzinfo=UTC)
        for offset in range(60):
            quantity = Decimal("2.00") + Decimal(offset % 12) / Decimal("2")
            add_sale(
                db,
                sale_number=f"FRC-CENTRAL-{offset}",
                branch_id=central_branch.id,
                created_by=manager.id,
                sale_datetime=start_date + timedelta(days=offset),
                product_id=rice.id,
                quantity=quantity,
                unit_price=Decimal("20.00"),
            )

        for offset in range(20):
            add_sale(
                db,
                sale_number=f"FRC-NORTH-{offset}",
                branch_id=north_branch.id,
                created_by=admin.id,
                sale_datetime=start_date + timedelta(days=offset),
                product_id=rice.id,
                quantity=Decimal("1.00"),
                unit_price=Decimal("20.00"),
            )

        db.commit()
        return {
            "central_branch_id": central_branch.id,
            "north_branch_id": north_branch.id,
            "category_id": category.id,
            "rice_id": rice.id,
            "sparse_id": sparse.id,
        }


def test_run_revenue_forecast_stores_output_and_returns_chart_data(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_forecast_data(db_session_factory)
    response = client.post(
        "/api/forecasts/run",
        json={
            "forecast_type": "revenue",
            "horizon_days": 7,
            "branch_id": ids["central_branch_id"],
            "as_of_date": "2026-05-20",
        },
        headers=login(client),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["insufficient_data"] is False
    assert payload["forecast_type"] == "revenue"
    assert payload["horizon_days"] == 7
    assert payload["trend_label"] in {"increasing", "stable"}
    assert Decimal(payload["forecast_value"]) > 0
    assert len(payload["historical_points"]) == 90
    assert len(payload["forecast_points"]) == 7
    assert payload["forecast"]["branch_id"] == ids["central_branch_id"]

    with db_session_factory() as db:
        forecasts = db.scalars(select(Forecast)).all()

    assert len(forecasts) == 1
    assert forecasts[0].forecast_type == ForecastType.REVENUE

    list_response = client.get("/api/forecasts?forecast_type=revenue", headers=login(client))
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == payload["forecast"]["id"]


def test_product_demand_forecast_and_product_history_endpoint(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_forecast_data(db_session_factory)
    run_response = client.post(
        "/api/forecasts/run",
        json={
            "forecast_type": "demand",
            "horizon_days": 30,
            "product_id": ids["rice_id"],
            "branch_id": ids["central_branch_id"],
            "as_of_date": "2026-05-20",
        },
        headers=login(client),
    )
    product_response = client.get(
        f"/api/forecasts/products/{ids['rice_id']}?branch_id={ids['central_branch_id']}",
        headers=login(client),
    )

    assert run_response.status_code == 200
    assert run_response.json()["insufficient_data"] is False
    assert run_response.json()["product_id"] == ids["rice_id"]
    assert run_response.json()["forecast_type"] == "demand"
    assert product_response.status_code == 200
    assert product_response.json()[0]["product_id"] == ids["rice_id"]
    assert product_response.json()[0]["forecast_type"] == "demand"


def test_insufficient_data_returns_clear_message_without_storing_forecast(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_forecast_data(db_session_factory)
    response = client.post(
        "/api/forecasts/run",
        json={
            "forecast_type": "demand",
            "horizon_days": 30,
            "product_id": ids["sparse_id"],
            "branch_id": ids["central_branch_id"],
            "as_of_date": "2026-05-20",
        },
        headers=login(client),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["insufficient_data"] is True
    assert payload["forecast"] is None
    assert "Not enough historical sales data" in payload["message"]
    assert payload["forecast_points"] == []

    with db_session_factory() as db:
        forecasts = db.scalars(select(Forecast)).all()

    assert forecasts == []


def test_store_manager_forecast_is_branch_scoped(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_forecast_data(db_session_factory)
    manager_headers = login(client, email="manager@hybridretail.test")
    run_response = client.post(
        "/api/forecasts/run",
        json={
            "forecast_type": "units",
            "horizon_days": 7,
            "as_of_date": "2026-05-20",
        },
        headers=manager_headers,
    )
    forbidden_response = client.get(
        f"/api/forecasts?branch_id={ids['north_branch_id']}",
        headers=manager_headers,
    )

    assert run_response.status_code == 200
    assert run_response.json()["branch_id"] == ids["central_branch_id"]
    assert forbidden_response.status_code == 403
