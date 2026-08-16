from pathlib import Path

from app.db.base import Base


def test_p1_migration_extends_hc1_local_chain() -> None:
    migration = Path(__file__).parents[1] / "alembic" / "versions" / "20260811_0008_multi_venture_scope.py"
    text = migration.read_text(encoding="utf-8")

    assert 'revision: str = "20260811_0008"' in text
    assert 'down_revision: str | None = "20260811_0007"' in text
    assert "P1 validation failed: inventory company mismatch" in text
    assert "P1 validation failed: invoice branch/company mismatch" in text
    assert "P1 validation failed: sale branch/company mismatch" in text


def test_company_aware_unique_constraints_are_declared() -> None:
    expected = {
        "branches": "uq_branches_company_name",
        "categories": "uq_categories_company_name",
        "suppliers": "uq_suppliers_company_name",
        "products": "uq_products_company_sku",
        "product_barcodes": "uq_product_barcodes_company_barcode",
        "sales": "uq_sales_company_sale_number",
        "purchase_orders": "uq_purchase_orders_company_po_number",
        "invoices": "uq_invoices_company_invoice_number",
        "customers": "uq_customers_company_phone",
    }

    for table_name, constraint_name in expected.items():
        names = {constraint.name for constraint in Base.metadata.tables[table_name].constraints}
        assert constraint_name in names, (table_name, names)
