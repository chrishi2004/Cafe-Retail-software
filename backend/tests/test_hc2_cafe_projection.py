from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.models import MenuCategory, MenuItem, PreparationArea
from app.services.cafe_cloud_publication import build_cafe_publication
from tests.p5_fixtures import seed_p5_test_data


def test_cafe_projection_contains_customer_fields_and_boolean_availability(
    db_session_factory: sessionmaker[Session],
    seed_auth_data: None,
) -> None:
    ids = seed_p5_test_data(db_session_factory)
    with db_session_factory() as db:
        category = MenuCategory(
            company_id=ids["cafe_company"],
            branch_id=None,
            name="Drinks",
            display_order=1,
            is_active=True,
        )
        db.add(category)
        db.flush()
        db.add(
            MenuItem(
                company_id=ids["cafe_company"],
                branch_id=ids["cafe_branch"],
                category_id=category.id,
                product_id=ids["cafe_product"],
                name="Latte",
                description="Customer description",
                selling_price=Decimal("175.00"),
                preparation_area=PreparationArea.BEVERAGE,
                available=True,
                is_active=True,
                display_order=1,
            )
        )
        db.commit()
        projection = build_cafe_publication(
            db,
            company_id=ids["cafe_company"],
            branch_id=ids["cafe_branch"],
            version=1,
        )

    assert projection.company_id == str(ids["cafe_company"])
    assert projection.branch_id == str(ids["cafe_branch"])
    assert any(row.name == "Latte" for row in projection.items)
    assert projection.availability
    assert all(isinstance(row.available, bool) for row in projection.availability)
    assert set(projection.items[0].model_dump().keys()) == {
        "source_menu_item_id",
        "source_product_id",
        "source_category_id",
        "name",
        "description",
        "image_reference",
        "selling_price",
        "preparation_area",
        "available",
        "display_order",
    }


def test_retail_scope_is_not_a_cafe_projection(
    db_session_factory: sessionmaker[Session],
    seed_auth_data: None,
) -> None:
    ids = seed_p5_test_data(db_session_factory)
    with db_session_factory() as db:
        with pytest.raises(HTTPException, match="Cafe"):
            build_cafe_publication(
                db,
                company_id=1,
                branch_id=ids["retail_branch"],
                version=1,
            )
