"""add ownership hierarchy and company scope

Revision ID: 20260811_0008
Revises: 20260811_0007
Create Date: 2026-08-11

P1 is an expand/backfill/validate migration. Existing operational rows are
assigned to the legacy Retail company without changing their primary keys,
amounts, dates, or business identifiers. Company-aware service enforcement is
completed in P2; the temporary server defaults on newly scoped legacy tables
keep the pre-P2 single-company write paths functional during this transition.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0008"
down_revision: str | None = "20260811_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_GROUP_ID = 1
LEGACY_RETAIL_COMPANY_ID = 1


def _drop_constraint(table: str, name: str) -> None:
    op.execute(sa.text(f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{name}"'))


def _add_company_scope(table: str) -> None:
    op.add_column(
        table,
        sa.Column(
            "company_id",
            sa.Integer(),
            nullable=False,
            server_default=str(LEGACY_RETAIL_COMPANY_ID),
        ),
    )
    op.create_foreign_key(
        f"fk_{table}_company_id_companies",
        table,
        "companies",
        ["company_id"],
        ["id"],
    )
    op.create_index(f"ix_{table}_company_id", table, ["company_id"], unique=False)


def _drop_company_scope(table: str) -> None:
    op.drop_index(f"ix_{table}_company_id", table_name=table)
    op.drop_constraint(f"fk_{table}_company_id_companies", table, type_="foreignkey")
    op.drop_column(table, "company_id")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("P1 multi-venture migration requires PostgreSQL for constraint-safe backfill.")

    # Ownership root. The fixed legacy IDs are used only during P1/P2 migration
    # compatibility and are removed from application write assumptions in P2.
    op.create_table(
        "business_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("legal_name", sa.String(length=240), nullable=True),
        sa.Column("pan", sa.String(length=20), nullable=True),
        sa.Column("default_currency", sa.String(length=3), server_default="INR", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_business_groups"),
        sa.UniqueConstraint("name", name="uq_business_groups_name"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO business_groups
                (id, name, legal_name, default_currency, is_active)
            VALUES
                (1, 'Kalpvrik Business Group', 'Kalpvrik Business Group', 'INR', true)
            ON CONFLICT (id) DO NOTHING
            """
        )
    )

    op.add_column(
        "companies",
        sa.Column("business_group_id", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "companies",
        sa.Column("business_type", sa.String(length=20), nullable=False, server_default="retail"),
    )
    op.add_column(
        "companies",
        sa.Column("slug", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_foreign_key(
        "fk_companies_business_group_id_business_groups",
        "companies",
        "business_groups",
        ["business_group_id"],
        ["id"],
    )

    # A clean migration chain has no seed data. Create the canonical Retail
    # workspace so every new non-null scope can be backfilled deterministically.
    op.execute(
        sa.text(
            """
            INSERT INTO companies
                (id, code, name, legal_name, trade_name, pan, default_currency,
                 is_active, business_group_id, business_type, slug, is_demo)
            SELECT
                1, 'HYBRID_RETAIL', 'Hybrid Retail Demo',
                'Hybrid Retail Demo Private Limited', 'Hybrid Retail Demo',
                NULL, 'INR', true, 1, 'retail', 'retail', true
            WHERE NOT EXISTS (SELECT 1 FROM companies)
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE companies
            SET business_group_id = 1,
                business_type = COALESCE(NULLIF(business_type, ''), 'retail'),
                slug = CASE
                    WHEN id = 1 THEN 'retail'
                    ELSE COALESCE(NULLIF(slug, ''), 'legacy-' || id::text)
                END
            """
        )
    )
    op.alter_column("companies", "slug", existing_type=sa.String(length=120), nullable=False)
    op.create_check_constraint(
        "ck_companies_business_type",
        "companies",
        "business_type IN ('retail', 'cafe')",
    )
    op.create_unique_constraint(
        "uq_companies_group_slug",
        "companies",
        ["business_group_id", "slug"],
    )
    op.create_index("ix_companies_business_group_id", "companies", ["business_group_id"], unique=False)
    op.create_index("ix_companies_business_type", "companies", ["business_type"], unique=False)

    # Ensure explicit legacy IDs do not leave serial sequences behind.
    op.execute(
        sa.text(
            """
            SELECT setval(
                pg_get_serial_sequence('business_groups', 'id'),
                GREATEST((SELECT COALESCE(MAX(id), 1) FROM business_groups), 1),
                true
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            SELECT setval(
                pg_get_serial_sequence('companies', 'id'),
                GREATEST((SELECT COALESCE(MAX(id), 1) FROM companies), 1),
                true
            )
            """
        )
    )

    # Branch and user ownership.
    op.add_column(
        "branches",
        sa.Column("company_id", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_foreign_key(
        "fk_branches_company_id_companies",
        "branches",
        "companies",
        ["company_id"],
        ["id"],
    )
    op.create_index("ix_branches_company_id", "branches", ["company_id"], unique=False)
    _drop_constraint("branches", "uq_branches_name")
    op.create_unique_constraint("uq_branches_company_name", "branches", ["company_id", "name"])

    op.add_column(
        "users",
        sa.Column("business_group_id", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("users", sa.Column("company_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_users_business_group_id_business_groups",
        "users",
        "business_groups",
        ["business_group_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_users_company_id_companies",
        "users",
        "companies",
        ["company_id"],
        ["id"],
    )
    op.create_index("ix_users_business_group_id", "users", ["business_group_id"], unique=False)
    op.create_index("ix_users_company_id", "users", ["company_id"], unique=False)

    # The old SQLAlchemy Enum is a CHECK constraint on PostgreSQL. Drop either
    # naming-convention spelling before introducing the expanded role set.
    _drop_constraint("users", "ck_users_user_role")
    _drop_constraint("users", "user_role")
    op.execute(
        sa.text(
            """
            UPDATE users
            SET business_group_id = 1,
                company_id = 1,
                token_version = COALESCE(token_version, 1) + 1
            """
        )
    )
    op.execute(
        sa.text(
            """
            WITH chosen AS (
                SELECT id
                FROM users
                WHERE role = 'admin' AND branch_id IS NULL
                ORDER BY id
                LIMIT 1
            )
            UPDATE users
            SET role = 'super_admin', company_id = NULL, branch_id = NULL
            WHERE id IN (SELECT id FROM chosen)
            """
        )
    )
    op.create_check_constraint(
        "ck_users_user_role",
        "users",
        "role IN ('super_admin', 'admin', 'store_manager', 'staff', 'order_taker', 'kitchen', 'analyst')",
    )
    op.create_check_constraint(
        "ck_users_role_scope",
        "users",
        "(role = 'super_admin' AND company_id IS NULL AND branch_id IS NULL) OR "
        "(role <> 'super_admin' AND company_id IS NOT NULL)",
    )

    # Add company scope to legacy operational/confidential roots.
    for table in (
        "categories",
        "suppliers",
        "products",
        "product_barcodes",
        "inventory",
        "stock_movements",
        "customer_ledger_entries",
        "customer_payments",
        "sales",
        "invoices",
        "purchase_orders",
        "forecasts",
        "ai_chat_sessions",
        "audit_logs",
    ):
        _add_company_scope(table)

    # Customers already had nullable company_id from the billing expansion.
    op.execute(sa.text("UPDATE customers SET company_id = 1 WHERE company_id IS NULL"))
    op.alter_column(
        "customers",
        "company_id",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="1",
    )

    # Backfill child-owned scope from the authoritative parent where practical.
    op.execute(
        sa.text(
            """
            UPDATE product_barcodes pb
            SET company_id = p.company_id
            FROM products p
            WHERE p.id = pb.product_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE customer_ledger_entries cle
            SET company_id = c.company_id
            FROM customers c
            WHERE c.id = cle.customer_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE customer_payments cp
            SET company_id = c.company_id
            FROM customers c
            WHERE c.id = cp.customer_id
            """
        )
    )

    # Replace legacy global uniqueness with venture-local uniqueness.
    for table, old_name in (
        ("categories", "uq_categories_name"),
        ("suppliers", "uq_suppliers_name"),
        ("products", "uq_products_sku"),
        ("product_barcodes", "uq_product_barcodes_barcode"),
        ("sales", "uq_sales_sale_number"),
        ("purchase_orders", "uq_purchase_orders_po_number"),
        ("customers", "uq_customers_phone"),
        ("customers", "uq_customers_email"),
        ("customers", "uq_customers_gstin"),
        ("invoices", "uq_invoices_invoice_number"),
    ):
        _drop_constraint(table, old_name)

    # primary_barcode was created as a unique index in 0004.
    op.execute(sa.text("DROP INDEX IF EXISTS ix_products_primary_barcode"))
    op.create_index("ix_products_primary_barcode", "products", ["primary_barcode"], unique=False)

    op.create_unique_constraint("uq_categories_company_name", "categories", ["company_id", "name"])
    op.create_unique_constraint("uq_suppliers_company_name", "suppliers", ["company_id", "name"])
    op.create_unique_constraint("uq_products_company_sku", "products", ["company_id", "sku"])
    op.create_unique_constraint(
        "uq_products_company_primary_barcode",
        "products",
        ["company_id", "primary_barcode"],
    )
    op.create_unique_constraint(
        "uq_product_barcodes_company_barcode",
        "product_barcodes",
        ["company_id", "barcode"],
    )
    op.create_unique_constraint("uq_sales_company_sale_number", "sales", ["company_id", "sale_number"])
    op.create_unique_constraint(
        "uq_purchase_orders_company_po_number",
        "purchase_orders",
        ["company_id", "po_number"],
    )
    op.create_unique_constraint("uq_customers_company_phone", "customers", ["company_id", "phone"])
    op.create_unique_constraint("uq_customers_company_email", "customers", ["company_id", "email"])
    op.create_unique_constraint("uq_customers_company_gstin", "customers", ["company_id", "gstin"])
    op.create_unique_constraint(
        "uq_invoices_company_invoice_number",
        "invoices",
        ["company_id", "invoice_number"],
    )

    # Release-blocking migration validation. Any mismatch means the migration
    # aborts transactionally instead of silently creating cross-venture rows.
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM branches b
                    LEFT JOIN companies c ON c.id = b.company_id
                    WHERE c.id IS NULL
                ) THEN
                    RAISE EXCEPTION 'P1 validation failed: orphan branch company';
                END IF;
                IF EXISTS (
                    SELECT 1 FROM inventory i
                    JOIN branches b ON b.id = i.branch_id
                    JOIN products p ON p.id = i.product_id
                    WHERE i.company_id <> b.company_id OR i.company_id <> p.company_id
                ) THEN
                    RAISE EXCEPTION 'P1 validation failed: inventory company mismatch';
                END IF;
                IF EXISTS (
                    SELECT 1 FROM invoices i
                    JOIN branches b ON b.id = i.branch_id
                    WHERE i.company_id <> b.company_id
                ) THEN
                    RAISE EXCEPTION 'P1 validation failed: invoice branch/company mismatch';
                END IF;
                IF EXISTS (
                    SELECT 1 FROM sales s
                    JOIN branches b ON b.id = s.branch_id
                    WHERE s.company_id <> b.company_id
                ) THEN
                    RAISE EXCEPTION 'P1 validation failed: sale branch/company mismatch';
                END IF;
            END $$
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("P1 multi-venture downgrade requires PostgreSQL.")

    # Downgrade intentionally fails if P1-era data now depends on duplicate
    # cross-company business identifiers; silently collapsing scope would be unsafe.
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT sku FROM products GROUP BY sku HAVING COUNT(*) > 1) THEN
                    RAISE EXCEPTION 'Cannot downgrade: duplicate SKU exists across companies';
                END IF;
                IF EXISTS (SELECT name FROM branches GROUP BY name HAVING COUNT(*) > 1) THEN
                    RAISE EXCEPTION 'Cannot downgrade: duplicate branch name exists across companies';
                END IF;
            END $$
            """
        )
    )

    op.drop_constraint("uq_invoices_company_invoice_number", "invoices", type_="unique")
    op.create_unique_constraint("uq_invoices_invoice_number", "invoices", ["invoice_number"])
    op.drop_constraint("uq_customers_company_gstin", "customers", type_="unique")
    op.drop_constraint("uq_customers_company_email", "customers", type_="unique")
    op.drop_constraint("uq_customers_company_phone", "customers", type_="unique")
    op.create_unique_constraint("uq_customers_phone", "customers", ["phone"])
    op.create_unique_constraint("uq_customers_email", "customers", ["email"])
    op.create_unique_constraint("uq_customers_gstin", "customers", ["gstin"])
    op.drop_constraint("uq_purchase_orders_company_po_number", "purchase_orders", type_="unique")
    op.create_unique_constraint("uq_purchase_orders_po_number", "purchase_orders", ["po_number"])
    op.drop_constraint("uq_sales_company_sale_number", "sales", type_="unique")
    op.create_unique_constraint("uq_sales_sale_number", "sales", ["sale_number"])
    op.drop_constraint("uq_product_barcodes_company_barcode", "product_barcodes", type_="unique")
    op.create_unique_constraint("uq_product_barcodes_barcode", "product_barcodes", ["barcode"])
    op.drop_constraint("uq_products_company_primary_barcode", "products", type_="unique")
    op.drop_index("ix_products_primary_barcode", table_name="products")
    op.create_index("ix_products_primary_barcode", "products", ["primary_barcode"], unique=True)
    op.drop_constraint("uq_products_company_sku", "products", type_="unique")
    op.create_unique_constraint("uq_products_sku", "products", ["sku"])
    op.drop_constraint("uq_suppliers_company_name", "suppliers", type_="unique")
    op.create_unique_constraint("uq_suppliers_name", "suppliers", ["name"])
    op.drop_constraint("uq_categories_company_name", "categories", type_="unique")
    op.create_unique_constraint("uq_categories_name", "categories", ["name"])

    op.alter_column("customers", "company_id", existing_type=sa.Integer(), nullable=True, server_default=None)
    for table in reversed(
        (
            "categories",
            "suppliers",
            "products",
            "product_barcodes",
            "inventory",
            "stock_movements",
            "customer_ledger_entries",
            "customer_payments",
            "sales",
            "invoices",
            "purchase_orders",
            "forecasts",
            "ai_chat_sessions",
            "audit_logs",
        )
    ):
        _drop_company_scope(table)

    op.drop_constraint("ck_users_role_scope", "users", type_="check")
    op.drop_constraint("ck_users_user_role", "users", type_="check")
    op.execute(sa.text("UPDATE users SET role = 'admin' WHERE role = 'super_admin'"))
    op.create_check_constraint(
        "ck_users_user_role",
        "users",
        "role IN ('admin', 'store_manager', 'staff', 'analyst')",
    )
    op.drop_index("ix_users_company_id", table_name="users")
    op.drop_index("ix_users_business_group_id", table_name="users")
    op.drop_constraint("fk_users_company_id_companies", "users", type_="foreignkey")
    op.drop_constraint("fk_users_business_group_id_business_groups", "users", type_="foreignkey")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_count")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "token_version")
    op.drop_column("users", "company_id")
    op.drop_column("users", "business_group_id")

    op.drop_constraint("uq_branches_company_name", "branches", type_="unique")
    op.create_unique_constraint("uq_branches_name", "branches", ["name"])
    op.drop_index("ix_branches_company_id", table_name="branches")
    op.drop_constraint("fk_branches_company_id_companies", "branches", type_="foreignkey")
    op.drop_column("branches", "company_id")

    op.drop_index("ix_companies_business_type", table_name="companies")
    op.drop_index("ix_companies_business_group_id", table_name="companies")
    op.drop_constraint("uq_companies_group_slug", "companies", type_="unique")
    op.drop_constraint("ck_companies_business_type", "companies", type_="check")
    op.drop_constraint("fk_companies_business_group_id_business_groups", "companies", type_="foreignkey")
    op.drop_column("companies", "is_demo")
    op.drop_column("companies", "slug")
    op.drop_column("companies", "business_type")
    op.drop_column("companies", "business_group_id")
    op.drop_table("business_groups")
