from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    AIChatMessage,
    AIChatSession,
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


def seed_ai_data(db_session_factory: sessionmaker[Session]) -> dict[str, int]:
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
            sku="AI-RICE-001",
            name="AI Rice 5kg",
            category_id=category.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("10.00"),
            selling_price=Decimal("15.00"),
            reorder_threshold=Decimal("5.00"),
            target_stock_level=Decimal("50.00"),
        )
        water = Product(
            sku="AI-WATER-001",
            name="AI Mineral Water",
            category_id=category.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("5.00"),
            selling_price=Decimal("8.00"),
            reorder_threshold=Decimal("10.00"),
            target_stock_level=Decimal("80.00"),
        )
        slow = Product(
            sku="AI-SLOW-001",
            name="AI Slow Soap",
            category_id=category.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("12.00"),
            selling_price=Decimal("18.00"),
            reorder_threshold=Decimal("10.00"),
            target_stock_level=Decimal("60.00"),
        )
        db.add_all([rice, water, slow])
        db.flush()

        db.add_all(
            [
                Inventory(
                    product_id=rice.id,
                    branch_id=central_branch.id,
                    quantity_on_hand=Decimal("0.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("2.00"),
                ),
                Inventory(
                    product_id=water.id,
                    branch_id=central_branch.id,
                    quantity_on_hand=Decimal("30.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("0.00"),
                ),
                Inventory(
                    product_id=slow.id,
                    branch_id=central_branch.id,
                    quantity_on_hand=Decimal("25.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("0.00"),
                ),
                Inventory(
                    product_id=rice.id,
                    branch_id=north_branch.id,
                    quantity_on_hand=Decimal("20.00"),
                    quantity_reserved=Decimal("0.00"),
                    quantity_on_order=Decimal("0.00"),
                ),
            ]
        )

        current_date = datetime.now(UTC).date()
        for offset in range(10):
            sale_datetime = datetime.combine(
                current_date - timedelta(days=offset),
                time(hour=10),
                tzinfo=UTC,
            )
            add_sale(
                db,
                sale_number=f"AI-CENTRAL-RICE-{offset}",
                branch_id=central_branch.id,
                created_by=manager.id,
                sale_datetime=sale_datetime,
                product_id=rice.id,
                quantity=Decimal("2.00"),
                unit_price=Decimal("15.00"),
            )
            add_sale(
                db,
                sale_number=f"AI-CENTRAL-WATER-{offset}",
                branch_id=central_branch.id,
                created_by=manager.id,
                sale_datetime=sale_datetime,
                product_id=water.id,
                quantity=Decimal("1.00"),
                unit_price=Decimal("8.00"),
            )
            add_sale(
                db,
                sale_number=f"AI-NORTH-RICE-{offset}",
                branch_id=north_branch.id,
                created_by=admin.id,
                sale_datetime=sale_datetime,
                product_id=rice.id,
                quantity=Decimal("5.00"),
                unit_price=Decimal("15.00"),
            )

        pending_order = PurchaseOrder(
            po_number="PO-AI-PENDING",
            supplier_id=supplier.id,
            branch_id=central_branch.id,
            status=PurchaseOrderStatus.PENDING_APPROVAL,
            order_date=current_date,
            expected_delivery_date=current_date + timedelta(days=3),
            total_amount=Decimal("180.00"),
            created_by=admin.id,
        )
        db.add(pending_order)
        db.commit()

        return {
            "central_branch_id": central_branch.id,
            "north_branch_id": north_branch.id,
            "pending_order_id": pending_order.id,
        }


def test_ai_assistant_answers_required_business_questions_and_stores_messages(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    seed_ai_data(db_session_factory)
    headers = login(client)
    questions = [
        ("What are today's sales?", "sales_summary", "get_sales_summary"),
        ("Which products are low in stock?", "low_stock_items", "get_low_stock_items"),
        ("Which items should I reorder today?", "reorder_recommendations", "get_reorder_recommendations"),
        ("What are the top-selling products this month?", "top_products", "get_top_products"),
        ("Which branch performed best?", "branch_performance", "get_sales_summary"),
        ("Which products are slow-moving?", "slow_moving_products", "get_slow_moving_products"),
        ("Summarize pending purchase orders.", "pending_purchase_orders", "get_pending_purchase_orders"),
        ("Forecast next week's demand.", "forecast_summary", "get_forecast_summary"),
    ]

    for question, expected_intent, expected_tool in questions:
        response = client.post("/api/ai/chat", json={"message": question}, headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["intent"] == expected_intent
        assert payload["response"]
        assert payload["tool_calls"][0]["name"] == expected_tool
        assert payload["requires_confirmation"] is False

    with db_session_factory() as db:
        sessions = db.scalars(select(AIChatSession)).all()
        messages = db.scalars(select(AIChatMessage)).all()

    assert len(sessions) == len(questions)
    assert len(messages) == len(questions) * 2


def test_ai_write_action_requires_confirmation_and_does_not_change_order(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_ai_data(db_session_factory)
    response = client.post(
        "/api/ai/chat",
        json={"message": "Approve PO-AI-PENDING now"},
        headers=login(client),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "confirmation_required"
    assert payload["requires_confirmation"] is True
    assert payload["tool_calls"] == []

    with db_session_factory() as db:
        purchase_order = db.get(PurchaseOrder, ids["pending_order_id"])

    assert purchase_order.status == PurchaseOrderStatus.PENDING_APPROVAL


def test_ai_respects_store_manager_branch_scope(client, db_session_factory: sessionmaker[Session]) -> None:
    seed_ai_data(db_session_factory)
    response = client.post(
        "/api/ai/chat",
        json={"message": "Which branch performed best?"},
        headers=login(client, email="manager@hybridretail.test"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "branch_performance"
    assert "Central Market" in payload["response"]
    assert "Northside Express" not in payload["response"]
    assert {row["branch_name"] for row in payload["tool_calls"][0]["data"]["branch_performance"]} == {
        "Central Market"
    }


def test_ai_sessions_are_user_scoped_and_staff_is_denied(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    seed_ai_data(db_session_factory)
    admin_headers = login(client)
    analyst_headers = login(client, email="analyst@hybridretail.test")
    staff_headers = login(client, email="staff@hybridretail.test")

    chat_response = client.post(
        "/api/ai/chat",
        json={"message": "Which products are low in stock?"},
        headers=admin_headers,
    )
    session_id = chat_response.json()["session_id"]
    list_response = client.get("/api/ai/sessions", headers=admin_headers)
    detail_response = client.get(f"/api/ai/sessions/{session_id}", headers=admin_headers)
    forbidden_detail = client.get(f"/api/ai/sessions/{session_id}", headers=analyst_headers)
    staff_response = client.post(
        "/api/ai/chat",
        json={"message": "What are today's sales?"},
        headers=staff_headers,
    )

    assert chat_response.status_code == 200
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == session_id
    assert detail_response.status_code == 200
    assert len(detail_response.json()["messages"]) == 2
    assert forbidden_detail.status_code == 403
    assert staff_response.status_code == 403
