from app.db.base import Base
from app.models import BusinessGroup, BusinessType, Company, UserRole


def test_business_group_company_branch_hierarchy_is_in_metadata() -> None:
    assert "business_groups" in Base.metadata.tables
    companies = Base.metadata.tables["companies"]
    branches = Base.metadata.tables["branches"]
    users = Base.metadata.tables["users"]

    assert "business_group_id" in companies.c
    assert "business_type" in companies.c
    assert "slug" in companies.c
    assert "company_id" in branches.c
    assert "business_group_id" in users.c
    assert "company_id" in users.c
    assert "token_version" in users.c


def test_required_operational_roots_are_company_scoped() -> None:
    scoped_tables = {
        "branches",
        "categories",
        "suppliers",
        "products",
        "product_barcodes",
        "inventory",
        "stock_movements",
        "customers",
        "customer_ledger_entries",
        "customer_payments",
        "sales",
        "invoices",
        "purchase_orders",
        "forecasts",
        "ai_chat_sessions",
        "audit_logs",
    }

    missing = sorted(name for name in scoped_tables if "company_id" not in Base.metadata.tables[name].c)
    assert missing == []


def test_role_and_business_type_enums_match_contract() -> None:
    assert {role.value for role in UserRole} == {
        "super_admin",
        "admin",
        "store_manager",
        "staff",
        "order_taker",
        "kitchen",
        "analyst",
    }
    assert {kind.value for kind in BusinessType} == {"retail", "cafe"}


def test_company_can_represent_retail_and_cafe_ventures() -> None:
    group = BusinessGroup(id=11, name="Group 11")
    retail = Company(
        id=21,
        business_group_id=group.id,
        business_type=BusinessType.RETAIL,
        slug="retail",
        code="RET-11",
        name="Retail 11",
        legal_name="Retail 11",
    )
    cafe = Company(
        id=22,
        business_group_id=group.id,
        business_type=BusinessType.CAFE,
        slug="cafe",
        code="CAF-11",
        name="Cafe 11",
        legal_name="Cafe 11",
    )

    assert retail.business_group_id == cafe.business_group_id == group.id
    assert retail.business_type is BusinessType.RETAIL
    assert cafe.business_type is BusinessType.CAFE
