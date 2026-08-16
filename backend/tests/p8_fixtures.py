from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    BusinessProfile,
    InvoiceSequence,
    InvoiceSequenceResetRule,
    InvoiceSequenceType,
    MenuItem,
    PaymentMode,
    PaymentModeType,
    PreparationArea,
    TaxMode,
    TaxRegistrationStatus,
)
from tests.p7_fixtures import cafe_headers, create_public_order, create_staff_dine_in_order, seed_p7


def seed_p8(factory: sessionmaker[Session]) -> dict[str, object]:
    ids = seed_p7(factory)
    with factory() as db:
        profile = db.scalar(select(BusinessProfile).where(BusinessProfile.company_id == ids["cafe_company"]))
        if profile is None:
            profile = BusinessProfile(
                company_id=ids["cafe_company"],
                legal_name="Test Cafe",
                trade_name="Test Cafe",
                tax_registration_status=TaxRegistrationStatus.UNREGISTERED,
                default_tax_mode=TaxMode.NON_GST,
                default_currency="INR",
            )
            db.add(profile)

        sequence = InvoiceSequence(
            company_id=ids["cafe_company"],
            branch_id=ids["cafe_branch"],
            invoice_type=InvoiceSequenceType.NON_GST_INVOICE,
            fiscal_year="2026-27",
            prefix="CAFE-",
            suffix=None,
            next_number=1,
            padding=5,
            reset_rule=InvoiceSequenceResetRule.FISCAL_YEAR,
            is_active=True,
        )
        cash = PaymentMode(
            company_id=ids["cafe_company"],
            name="Cash",
            mode_type=PaymentModeType.CASH,
            requires_reference=False,
            display_order=1,
            is_active=True,
        )
        upi = PaymentMode(
            company_id=ids["cafe_company"],
            name="UPI",
            mode_type=PaymentModeType.UPI,
            requires_reference=True,
            display_order=2,
            is_active=True,
        )
        db.add_all([sequence, cash, upi])
        db.flush()

        unlinked = MenuItem(
            company_id=ids["cafe_company"],
            branch_id=ids["cafe_branch"],
            category_id=ids["menu_category"],
            product_id=None,
            name="Fresh Sandwich",
            description="Prepared to order",
            selling_price=Decimal("120.00"),
            preparation_area=PreparationArea.KITCHEN,
            available=True,
            is_active=True,
            display_order=2,
        )
        db.add(unlinked)
        db.commit()
        ids.update(
            {
                "cash_mode": cash.id,
                "upi_mode": upi.id,
                "unlinked_menu_item": unlinked.id,
                "unlinked_menu_item_public_id": unlinked.public_id,
            }
        )
    return ids


def advance_order_to_served(client: TestClient, headers: dict[str, str], public_id: str) -> dict:
    current = client.get(f"/api/cafe/orders/{public_id}", headers=headers)
    assert current.status_code == 200, current.text
    order = current.json()
    for action in ("accept", "start-preparing", "mark-ready", "serve"):
        response = client.post(
            f"/api/cafe/orders/{public_id}/{action}",
            headers=headers,
            json={"expected_version": order["version"]},
        )
        assert response.status_code == 200, response.text
        order = response.json()
    return order


def create_mixed_served_table_orders(client: TestClient, ids: dict[str, object]) -> tuple[dict, dict]:
    headers = cafe_headers(client, "order_taker")
    public = create_public_order(client, ids, key="p8-qr-order-0001")
    assert public.status_code == 201, public.text
    public_order = advance_order_to_served(client, headers, public.json()["public_id"])

    staff = create_staff_dine_in_order(client, ids, headers=headers)
    assert staff.status_code == 201, staff.text
    staff_order = advance_order_to_served(client, headers, staff.json()["public_id"])
    return public_order, staff_order


def create_unlinked_served_order(client: TestClient, ids: dict[str, object]) -> dict:
    headers = cafe_headers(client, "order_taker")
    response = client.post(
        "/api/cafe/orders",
        headers=headers,
        json={
            "order_type": "dine_in",
            "branch_id": ids["cafe_branch"],
            "table_session_public_id": ids["table_session_public_id"],
            "items": [
                {
                    "menu_item_public_id": ids["unlinked_menu_item_public_id"],
                    "quantity": 1,
                    "notes": "Toast well",
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return advance_order_to_served(client, headers, response.json()["public_id"])
