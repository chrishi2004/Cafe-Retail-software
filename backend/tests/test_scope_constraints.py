from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    Branch,
    BusinessGroup,
    BusinessType,
    Category,
    Company,
    Product,
    Supplier,
    User,
    UserRole,
)


def _companies(db: Session) -> tuple[Company, Company]:
    group = BusinessGroup(id=101, name="Constraint Group")
    retail = Company(
        id=101,
        business_group_id=group.id,
        business_type=BusinessType.RETAIL,
        slug="retail-constraints",
        code="RET-C",
        name="Retail Constraints",
        legal_name="Retail Constraints",
    )
    cafe = Company(
        id=102,
        business_group_id=group.id,
        business_type=BusinessType.CAFE,
        slug="cafe-constraints",
        code="CAF-C",
        name="Cafe Constraints",
        legal_name="Cafe Constraints",
    )
    db.add_all([group, retail, cafe])
    db.flush()
    return retail, cafe


def test_branch_names_are_unique_per_company_not_globally(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as db:
        retail, cafe = _companies(db)
        db.add_all(
            [
                Branch(company_id=retail.id, name="Main"),
                Branch(company_id=cafe.id, name="Main"),
            ]
        )
        db.commit()

        db.add(Branch(company_id=retail.id, name="Main"))
        with pytest.raises(IntegrityError):
            db.commit()


def test_sku_is_unique_inside_company_but_reusable_across_companies(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as db:
        retail, cafe = _companies(db)
        retail_category = Category(company_id=retail.id, name="Beverages")
        cafe_category = Category(company_id=cafe.id, name="Beverages")
        retail_supplier = Supplier(company_id=retail.id, name="Supplier")
        cafe_supplier = Supplier(company_id=cafe.id, name="Supplier")
        db.add_all([retail_category, cafe_category, retail_supplier, cafe_supplier])
        db.flush()

        db.add_all(
            [
                Product(
                    company_id=retail.id,
                    sku="SHARED-SKU",
                    name="Retail Product",
                    category_id=retail_category.id,
                    supplier_id=retail_supplier.id,
                    unit_cost=Decimal("10"),
                    selling_price=Decimal("15"),
                ),
                Product(
                    company_id=cafe.id,
                    sku="SHARED-SKU",
                    name="Cafe Product",
                    category_id=cafe_category.id,
                    supplier_id=cafe_supplier.id,
                    unit_cost=Decimal("10"),
                    selling_price=Decimal("15"),
                ),
            ]
        )
        db.commit()

        db.add(
            Product(
                company_id=retail.id,
                sku="SHARED-SKU",
                name="Duplicate Retail Product",
                category_id=retail_category.id,
                supplier_id=retail_supplier.id,
                unit_cost=Decimal("10"),
                selling_price=Decimal("15"),
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_user_role_scope_constraint_requires_company_for_normal_users(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as db:
        retail, _ = _companies(db)
        admin = User(
            business_group_id=101,
            company_id=retail.id,
            name="Venture Admin",
            email="venture-admin@example.test",
            password_hash="not-a-real-password-hash",
            role=UserRole.ADMIN,
        )
        owner = User(
            business_group_id=101,
            company_id=None,
            branch_id=None,
            name="Owner",
            email="owner@example.test",
            password_hash="not-a-real-password-hash",
            role=UserRole.SUPER_ADMIN,
        )
        db.add_all([admin, owner])
        db.commit()

        assert admin.company_id == retail.id
        assert owner.company_id is None

        db.add(
            User(
                business_group_id=101,
                company_id=None,
                name="Invalid Admin",
                email="invalid-admin@example.test",
                password_hash="not-a-real-password-hash",
                role=UserRole.ADMIN,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
