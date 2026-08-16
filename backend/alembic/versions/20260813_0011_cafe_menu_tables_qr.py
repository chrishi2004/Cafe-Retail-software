"""add Cafe menu tables secure QR and table sessions

Revision ID: 20260813_0011
Revises: 20260813_0010
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0011"
down_revision: str | None = "20260813_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "menu_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("display_order >= 0", name="ck_menu_categories_display_order_non_negative"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_menu_categories_company_id", "menu_categories", ["company_id"])
    op.create_index("ix_menu_categories_branch_id", "menu_categories", ["branch_id"])
    op.create_index(
        "uq_menu_categories_company_global_name",
        "menu_categories",
        ["company_id", "name"],
        unique=True,
        postgresql_where=sa.text("branch_id IS NULL"),
    )
    op.create_index(
        "uq_menu_categories_company_branch_name",
        "menu_categories",
        ["company_id", "branch_id", "name"],
        unique=True,
        postgresql_where=sa.text("branch_id IS NOT NULL"),
    )

    op.create_table(
        "menu_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_reference", sa.String(length=500), nullable=True),
        sa.Column("selling_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("preparation_area", sa.String(length=20), server_default="none", nullable=False),
        sa.Column("available", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("selling_price >= 0", name="ck_menu_items_selling_price_non_negative"),
        sa.CheckConstraint("display_order >= 0", name="ck_menu_items_display_order_non_negative"),
        sa.CheckConstraint("version >= 1", name="ck_menu_items_version_positive"),
        sa.CheckConstraint(
            "preparation_area IN ('kitchen', 'beverage', 'counter', 'none')",
            name="ck_menu_items_preparation_area",
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["menu_categories.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_menu_items_company_id", "menu_items", ["company_id"])
    op.create_index("ix_menu_items_branch_id", "menu_items", ["branch_id"])
    op.create_index("ix_menu_items_category_id", "menu_items", ["category_id"])
    op.create_index("ix_menu_items_product_id", "menu_items", ["product_id"])

    op.create_table(
        "cafe_tables",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("table_code", sa.String(length=60), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("area", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("capacity IS NULL OR capacity > 0", name="ck_cafe_tables_capacity_positive"),
        sa.CheckConstraint("version >= 1", name="ck_cafe_tables_version_positive"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "branch_id", "table_code", name="uq_cafe_tables_company_branch_code"),
    )
    op.create_index("ix_cafe_tables_company_id", "cafe_tables", ["company_id"])
    op.create_index("ix_cafe_tables_branch_id", "cafe_tables", ["branch_id"])

    op.create_table(
        "table_qr_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.Integer(), nullable=False),
        sa.Column("public_reference", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["table_id"], ["cafe_tables.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_reference", name="uq_table_qr_tokens_public_reference"),
        sa.UniqueConstraint("token_hash", name="uq_table_qr_tokens_token_hash"),
    )
    op.create_index("ix_table_qr_tokens_company_id", "table_qr_tokens", ["company_id"])
    op.create_index("ix_table_qr_tokens_branch_id", "table_qr_tokens", ["branch_id"])
    op.create_index("ix_table_qr_tokens_table_id", "table_qr_tokens", ["table_id"])
    op.create_index("ix_table_qr_tokens_public_reference", "table_qr_tokens", ["public_reference"])
    op.create_index("ix_table_qr_tokens_revoked_at", "table_qr_tokens", ["revoked_at"])

    op.create_table(
        "table_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.Integer(), nullable=False),
        sa.Column("session_type", sa.String(length=20), server_default="dine_in", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("opened_by", sa.Integer(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_by", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("session_type IN ('dine_in', 'takeaway', 'counter')", name="ck_table_sessions_type"),
        sa.CheckConstraint(
            "status IN ('open', 'bill_requested', 'billed', 'closed', 'cancelled')",
            name="ck_table_sessions_status",
        ),
        sa.CheckConstraint("version >= 1", name="ck_table_sessions_version_positive"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["table_id"], ["cafe_tables.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opened_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["closed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_table_sessions_public_id"),
    )
    op.create_index("ix_table_sessions_company_id", "table_sessions", ["company_id"])
    op.create_index("ix_table_sessions_branch_id", "table_sessions", ["branch_id"])
    op.create_index("ix_table_sessions_table_id", "table_sessions", ["table_id"])
    op.create_index("ix_table_sessions_public_id", "table_sessions", ["public_id"])
    op.create_index("ix_table_sessions_status", "table_sessions", ["status"])
    op.create_index(
        "uq_table_sessions_one_active_per_table",
        "table_sessions",
        ["table_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('open', 'bill_requested', 'billed')"),
    )


def downgrade() -> None:
    op.drop_index("uq_table_sessions_one_active_per_table", table_name="table_sessions")
    op.drop_index("ix_table_sessions_status", table_name="table_sessions")
    op.drop_index("ix_table_sessions_public_id", table_name="table_sessions")
    op.drop_index("ix_table_sessions_table_id", table_name="table_sessions")
    op.drop_index("ix_table_sessions_branch_id", table_name="table_sessions")
    op.drop_index("ix_table_sessions_company_id", table_name="table_sessions")
    op.drop_table("table_sessions")

    op.drop_index("ix_table_qr_tokens_revoked_at", table_name="table_qr_tokens")
    op.drop_index("ix_table_qr_tokens_public_reference", table_name="table_qr_tokens")
    op.drop_index("ix_table_qr_tokens_table_id", table_name="table_qr_tokens")
    op.drop_index("ix_table_qr_tokens_branch_id", table_name="table_qr_tokens")
    op.drop_index("ix_table_qr_tokens_company_id", table_name="table_qr_tokens")
    op.drop_table("table_qr_tokens")

    op.drop_index("ix_cafe_tables_branch_id", table_name="cafe_tables")
    op.drop_index("ix_cafe_tables_company_id", table_name="cafe_tables")
    op.drop_table("cafe_tables")

    op.drop_index("ix_menu_items_product_id", table_name="menu_items")
    op.drop_index("ix_menu_items_category_id", table_name="menu_items")
    op.drop_index("ix_menu_items_branch_id", table_name="menu_items")
    op.drop_index("ix_menu_items_company_id", table_name="menu_items")
    op.drop_table("menu_items")

    op.drop_index("uq_menu_categories_company_branch_name", table_name="menu_categories")
    op.drop_index("uq_menu_categories_company_global_name", table_name="menu_categories")
    op.drop_index("ix_menu_categories_branch_id", table_name="menu_categories")
    op.drop_index("ix_menu_categories_company_id", table_name="menu_categories")
    op.drop_table("menu_categories")
