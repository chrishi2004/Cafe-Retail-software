from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    AIChatMessage,
    Branch,
    Category,
    Forecast,
    Inventory,
    Product,
    Sale,
    SaleItem,
    StockMovement,
    StockMovementType,
    Supplier,
    User,
)
from app.services import ai as ai_service


def login(client, email: str = "admin@hybridretail.test") -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "RetailDemo@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def supplier_payload(name: str = "Workflow Supply Co") -> dict[str, object]:
    return {
        "name": name,
        "contact_person": "Maya Iyer",
        "email": "workflow-supply@example.com",
        "phone": "9876500111",
        "address": "QA Commerce Park",
        "payment_terms": "Net 15",
        "lead_time_days": 3,
        "is_active": True,
    }


def product_payload(category_id: int, supplier_id: int, sku: str = "WF-RICE-001") -> dict[str, object]:
    return {
        "sku": sku,
        "name": "Workflow Rice 5kg",
        "description": "Workflow test staple product",
        "category_id": category_id,
        "supplier_id": supplier_id,
        "unit_cost": "10.00",
        "selling_price": "15.00",
        "reorder_threshold": "5.00",
        "target_stock_level": "40.00",
        "is_active": True,
    }


def get_central_branch_id(db_session_factory: sessionmaker[Session]) -> int:
    with db_session_factory() as db:
        branch = db.scalar(select(Branch).where(Branch.name == "Central Market"))
        assert branch is not None
        return branch.id


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


def seed_forecast_and_ai_data(db_session_factory: sessionmaker[Session]) -> dict[str, int]:
    with db_session_factory() as db:
        branch = db.scalar(select(Branch).where(Branch.name == "Central Market"))
        manager = db.scalar(select(User).where(User.email == "manager@hybridretail.test"))
        assert branch is not None
        assert manager is not None

        category = Category(name="Workflow Forecast Grocery", description="Forecast QA category")
        supplier = Supplier(
            name="Workflow Forecast Supplier",
            contact_person="Nisha Das",
            email="workflow-forecast@example.com",
            lead_time_days=4,
        )
        db.add_all([category, supplier])
        db.flush()

        forecast_product = Product(
            sku="WF-FORECAST-001",
            name="Workflow Forecast Almonds",
            category_id=category.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("25.00"),
            selling_price=Decimal("40.00"),
            reorder_threshold=Decimal("5.00"),
            target_stock_level=Decimal("50.00"),
        )
        sparse_product = Product(
            sku="WF-SPARSE-001",
            name="Workflow Sparse Tea",
            category_id=category.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("8.00"),
            selling_price=Decimal("12.00"),
            reorder_threshold=Decimal("5.00"),
            target_stock_level=Decimal("30.00"),
        )
        db.add_all([forecast_product, sparse_product])
        db.flush()

        db.add_all(
            [
                Inventory(
                    product_id=forecast_product.id,
                    branch_id=branch.id,
                    quantity_on_hand=Decimal("2.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("0.00"),
                ),
                Inventory(
                    product_id=sparse_product.id,
                    branch_id=branch.id,
                    quantity_on_hand=Decimal("20.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("0.00"),
                ),
            ]
        )

        start_date = datetime(2026, 3, 20, 10, 0, tzinfo=UTC)
        for offset in range(55):
            quantity = Decimal("2.00") + Decimal(offset % 5)
            add_sale(
                db,
                sale_number=f"WF-FRC-{offset:03d}",
                branch_id=branch.id,
                created_by=manager.id,
                sale_datetime=start_date + timedelta(days=offset),
                product_id=forecast_product.id,
                quantity=quantity,
                unit_price=Decimal("40.00"),
            )

        db.commit()
        return {
            "branch_id": branch.id,
            "forecast_product_id": forecast_product.id,
            "sparse_product_id": sparse_product.id,
        }


def test_complete_operational_workflow_from_master_data_to_received_stock(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    admin_headers = login(client)
    staff_headers = login(client, email="staff@hybridretail.test")
    analyst_headers = login(client, email="analyst@hybridretail.test")

    supplier_response = client.post("/api/suppliers", json=supplier_payload(), headers=admin_headers)
    category_response = client.post(
        "/api/categories",
        json={"name": "Workflow Grocery", "description": "QA workflow category"},
        headers=admin_headers,
    )
    assert supplier_response.status_code == 201
    assert category_response.status_code == 201

    product_create_payload = product_payload(
        category_id=category_response.json()["id"],
        supplier_id=supplier_response.json()["id"],
    )
    product_response = client.post("/api/products", json=product_create_payload, headers=admin_headers)
    analyst_response = client.post("/api/products", json=product_create_payload, headers=analyst_headers)
    assert product_response.status_code == 201
    assert analyst_response.status_code == 403

    branch_id = get_central_branch_id(db_session_factory)
    product_id = product_response.json()["id"]
    with db_session_factory() as db:
        db.add(
            Inventory(
                product_id=product_id,
                branch_id=branch_id,
                quantity_on_hand=Decimal("6.00"),
                quantity_reserved=Decimal("0.00"),
                quantity_on_order=Decimal("0.00"),
            )
        )
        db.commit()

    adjustment_response = client.post(
        "/api/inventory/adjustments",
        json={
            "product_id": product_id,
            "branch_id": branch_id,
            "quantity_change": "3.00",
            "reason": "Part 16 cycle count correction",
        },
        headers=admin_headers,
    )
    assert adjustment_response.status_code == 200
    assert adjustment_response.json()["inventory"]["quantity_on_hand"] == "9.00"
    assert adjustment_response.json()["movement"]["movement_type"] == "manual_adjustment"

    sale_response = client.post(
        "/api/sales",
        json={
            "branch_id": branch_id,
            "sale_datetime": "2026-05-18T10:15:00+00:00",
            "tax_rate": "0.00",
            "items": [
                {
                    "product_id": product_id,
                    "quantity": "4.00",
                    "discount_amount": "0.00",
                }
            ],
        },
        headers=staff_headers,
    )
    assert sale_response.status_code == 200
    assert sale_response.json()["total_amount"] == "60.00"
    assert sale_response.json()["units_sold"] == "4.00"

    low_stock_response = client.get(f"/api/inventory/low-stock?branch_id={branch_id}", headers=admin_headers)
    assert low_stock_response.status_code == 200
    assert any(row["product_id"] == product_id for row in low_stock_response.json())

    reorder_response = client.get(
        f"/api/inventory/reorder-recommendations?branch_id={branch_id}&lookback_days=7&as_of_date=2026-05-18",
        headers=admin_headers,
    )
    assert reorder_response.status_code == 200
    assert all(Decimal(row["suggested_reorder_quantity"]) >= 0 for row in reorder_response.json())
    reorder_row = next(row for row in reorder_response.json() if row["product_id"] == product_id)
    assert reorder_row["current_stock"] == "5.00"
    assert reorder_row["suggested_reorder_quantity"] != "-0.00"

    with db_session_factory() as db:
        inventory_after_sale = db.scalar(
            select(Inventory).where(Inventory.product_id == product_id, Inventory.branch_id == branch_id)
        )
        movements_after_sale = db.scalars(
            select(StockMovement).where(StockMovement.product_id == product_id).order_by(StockMovement.id)
        ).all()
    assert inventory_after_sale is not None
    assert inventory_after_sale.quantity_on_hand == Decimal("5.00")
    assert [movement.movement_type for movement in movements_after_sale] == [
        StockMovementType.MANUAL_ADJUSTMENT,
        StockMovementType.SALE,
    ]
    assert [movement.quantity_change for movement in movements_after_sale] == [
        Decimal("3.00"),
        Decimal("-4.00"),
    ]

    po_response = client.post(
        "/api/purchase-orders",
        json={
            "supplier_id": supplier_response.json()["id"],
            "branch_id": branch_id,
            "order_date": "2026-05-18",
            "expected_delivery_date": "2026-05-21",
            "items": [{"product_id": product_id, "quantity_ordered": "6.00"}],
        },
        headers=admin_headers,
    )
    assert po_response.status_code == 200
    assert po_response.json()["status"] == "draft"
    order_id = po_response.json()["id"]
    item_id = po_response.json()["items"][0]["id"]

    with db_session_factory() as db:
        inventory_after_draft = db.scalar(
            select(Inventory).where(Inventory.product_id == product_id, Inventory.branch_id == branch_id)
        )
        movement_count_after_draft = len(
            db.scalars(select(StockMovement).where(StockMovement.product_id == product_id)).all()
        )
    assert inventory_after_draft is not None
    assert inventory_after_draft.quantity_on_hand == Decimal("5.00")
    assert inventory_after_draft.quantity_on_order == Decimal("0.00")
    assert movement_count_after_draft == 2

    assert client.post(f"/api/purchase-orders/{order_id}/submit", headers=admin_headers).status_code == 200
    approve_response = client.post(f"/api/purchase-orders/{order_id}/approve", headers=admin_headers)
    invalid_approve_response = client.post(f"/api/purchase-orders/{order_id}/approve", headers=admin_headers)
    ordered_response = client.post(f"/api/purchase-orders/{order_id}/mark-ordered", headers=admin_headers)
    receive_response = client.post(
        f"/api/purchase-orders/{order_id}/receive",
        json={"items": [{"item_id": item_id, "quantity_received": "6.00"}]},
        headers=admin_headers,
    )

    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"
    assert invalid_approve_response.status_code == 400
    assert ordered_response.status_code == 200
    assert receive_response.status_code == 200
    assert receive_response.json()["status"] == "received"

    with db_session_factory() as db:
        final_inventory = db.scalar(
            select(Inventory).where(Inventory.product_id == product_id, Inventory.branch_id == branch_id)
        )
        final_movements = db.scalars(
            select(StockMovement).where(StockMovement.product_id == product_id).order_by(StockMovement.id)
        ).all()
    assert final_inventory is not None
    assert final_inventory.quantity_on_hand == Decimal("11.00")
    assert final_inventory.quantity_on_order == Decimal("0.00")
    assert final_movements[-1].movement_type == StockMovementType.PURCHASE_RECEIVED
    assert final_movements[-1].quantity_change == Decimal("6.00")


def test_forecasting_and_ai_use_real_data_and_handle_missing_history(
    client,
    db_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ai_service.settings, "openai_api_key", None)
    ids = seed_forecast_and_ai_data(db_session_factory)
    headers = login(client)

    enough_data_response = client.post(
        "/api/forecasts/run",
        json={
            "forecast_type": "demand",
            "horizon_days": 7,
            "product_id": ids["forecast_product_id"],
            "branch_id": ids["branch_id"],
            "as_of_date": "2026-05-20",
        },
        headers=headers,
    )
    insufficient_data_response = client.post(
        "/api/forecasts/run",
        json={
            "forecast_type": "demand",
            "horizon_days": 30,
            "product_id": ids["sparse_product_id"],
            "branch_id": ids["branch_id"],
            "as_of_date": "2026-05-20",
        },
        headers=headers,
    )

    assert enough_data_response.status_code == 200
    assert enough_data_response.json()["insufficient_data"] is False
    assert enough_data_response.json()["forecast_points"]
    assert Decimal(enough_data_response.json()["forecast_value"]) > 0

    assert insufficient_data_response.status_code == 200
    assert insufficient_data_response.json()["insufficient_data"] is True
    assert insufficient_data_response.json()["forecast"] is None
    assert "Not enough historical sales data" in insufficient_data_response.json()["message"]

    ai_response = client.post(
        "/api/ai/chat",
        json={"message": "Which products are low in stock?"},
        headers=headers,
    )
    assert ai_response.status_code == 200
    payload = ai_response.json()
    assert payload["intent"] == "low_stock_items"
    assert payload["requires_confirmation"] is False
    assert payload["tool_calls"][0]["name"] == "get_low_stock_items"
    assert "database_backed_tools_for_numbers" in payload["assistant_message"]["metadata_json"]["guardrails"]

    low_stock_rows = payload["tool_calls"][0]["data"]["items"]
    forecast_product_row = next(row for row in low_stock_rows if row["product_id"] == ids["forecast_product_id"])
    assert forecast_product_row["product_name"] == "Workflow Forecast Almonds"
    assert forecast_product_row["quantity_on_hand"] == "2.00"
    assert forecast_product_row["reorder_threshold"] == "5.00"

    with db_session_factory() as db:
        stored_forecasts = db.scalars(select(Forecast)).all()
        stored_ai_messages = db.scalars(select(AIChatMessage)).all()

    assert len(stored_forecasts) == 1
    assert len(stored_ai_messages) == 2
