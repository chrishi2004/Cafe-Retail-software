from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.models import Branch, BusinessType, Category, Company, Inventory, Product, Supplier, User, UserRole

TEST_PASSWORD = "RetailDemo@123"


def seed_two_ventures(factory: sessionmaker[Session]) -> dict[str, int]:
    with factory() as db:
        retail = db.get(Company, 1)
        assert retail is not None
        retail_branch = db.query(Branch).filter(Branch.company_id == retail.id).first()
        assert retail_branch is not None

        cafe = Company(
            id=2,
            business_group_id=retail.business_group_id,
            business_type=BusinessType.CAFE,
            slug="cafe",
            code="TEST_CAFE",
            name="Test Cafe",
            legal_name="Test Cafe",
            is_demo=True,
        )
        cafe_branch = Branch(company_id=2, name="Cafe Main", city="Bengaluru")
        retail_second_branch = Branch(company_id=1, name="Retail North", city="Bengaluru")
        db.add_all([cafe, cafe_branch, retail_second_branch])
        db.flush()

        cafe_admin = User(
            business_group_id=retail.business_group_id,
            company_id=2,
            name="Cafe Admin",
            email="cafe.admin@example.test",
            password_hash=hash_password(TEST_PASSWORD),
            role=UserRole.ADMIN,
        )
        owner = User(
            business_group_id=retail.business_group_id,
            company_id=None,
            branch_id=None,
            name="Group Owner",
            email="owner@example.test",
            password_hash=hash_password(TEST_PASSWORD),
            role=UserRole.SUPER_ADMIN,
        )
        db.add_all([cafe_admin, owner])
        db.flush()

        retail_category = Category(company_id=1, name="Shared Category")
        cafe_category = Category(company_id=2, name="Shared Category")
        retail_supplier = Supplier(company_id=1, name="Shared Supplier")
        cafe_supplier = Supplier(company_id=2, name="Shared Supplier")
        db.add_all([retail_category, cafe_category, retail_supplier, cafe_supplier])
        db.flush()

        retail_product = Product(
            company_id=1,
            sku="SHARED-SKU",
            name="Retail Secret Product",
            category_id=retail_category.id,
            supplier_id=retail_supplier.id,
            unit_cost=Decimal("10"),
            selling_price=Decimal("15"),
        )
        cafe_product = Product(
            company_id=2,
            sku="SHARED-SKU",
            name="Cafe Product",
            category_id=cafe_category.id,
            supplier_id=cafe_supplier.id,
            unit_cost=Decimal("20"),
            selling_price=Decimal("30"),
        )
        db.add_all([retail_product, cafe_product])
        db.flush()
        db.add_all([
            Inventory(company_id=1, product_id=retail_product.id, branch_id=retail_branch.id, quantity_on_hand=Decimal("5")),
            Inventory(company_id=2, product_id=cafe_product.id, branch_id=cafe_branch.id, quantity_on_hand=Decimal("7")),
        ])
        db.commit()

        return {
            "cafe_company": 2,
            "retail_branch": retail_branch.id,
            "retail_second_branch": retail_second_branch.id,
            "cafe_branch": cafe_branch.id,
            "cafe_admin": cafe_admin.id,
            "owner": owner.id,
            "retail_category": retail_category.id,
            "cafe_category": cafe_category.id,
            "retail_supplier": retail_supplier.id,
            "cafe_supplier": cafe_supplier.id,
            "retail_product": retail_product.id,
            "cafe_product": cafe_product.id,
        }


def login_headers(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
