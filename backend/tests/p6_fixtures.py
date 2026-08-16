from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.core.scope import scope_context_for_user
from app.models import CafeTable, MenuCategory, MenuItem, PreparationArea, User
from app.schemas.cafe import QRRotateRequest, TableSessionOpen
from app.services.cafe import open_table_session, rotate_table_qr
from tests.p5_fixtures import seed_p5_test_data


def seed_p6_public_ordering(factory: sessionmaker[Session]) -> dict[str, object]:
    ids = seed_p5_test_data(factory)
    with factory() as db:
        admin = db.get(User, ids["cafe_admin"])
        assert admin is not None
        scope = scope_context_for_user(admin)

        category = MenuCategory(
            company_id=ids["cafe_company"],
            branch_id=ids["cafe_branch"],
            name="Guest Menu",
            display_order=1,
            is_active=True,
        )
        table = CafeTable(
            company_id=ids["cafe_company"],
            branch_id=ids["cafe_branch"],
            table_code="P6-T01",
            display_name="Window Table",
            capacity=4,
            is_active=True,
        )
        db.add_all([category, table])
        db.flush()
        item = MenuItem(
            company_id=ids["cafe_company"],
            branch_id=ids["cafe_branch"],
            category_id=category.id,
            product_id=ids["cafe_product"],
            name="Cafe Latte",
            description="Fresh coffee",
            selling_price=Decimal("180.00"),
            preparation_area=PreparationArea.BEVERAGE,
            available=True,
            is_active=True,
            display_order=1,
        )
        db.add(item)
        db.commit()
        db.refresh(category)
        db.refresh(item)
        db.refresh(table)

        qr = rotate_table_qr(
            db,
            scope=scope,
            table_id=table.id,
            payload=QRRotateRequest(expires_in_days=30),
            user=admin,
            request=None,
        )
        session = open_table_session(
            db,
            scope=scope,
            payload=TableSessionOpen(table_id=table.id),
            user=admin,
            request=None,
        )
        return {
            **ids,
            "menu_category": category.id,
            "menu_category_public_id": category.public_id,
            "menu_item": item.id,
            "menu_item_public_id": item.public_id,
            "table": table.id,
            "table_session": session.id,
            "table_session_public_id": session.public_id,
            "raw_qr": qr.raw_token,
        }
