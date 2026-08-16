"""upgrade product catalog for Indian retail billing

Revision ID: 20260521_0004
Revises: 20260521_0003
Create Date: 2026-05-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260521_0004"
down_revision: str | None = "20260521_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.add_column("products", sa.Column("gst_rate_id", sa.Integer(), nullable=True))
        op.add_column("products", sa.Column("hsn_sac_code", sa.String(length=20), nullable=True))
        op.add_column("products", sa.Column("cess_rate_percent", sa.Numeric(5, 2), nullable=False, server_default="0"))
        op.add_column("products", sa.Column("primary_barcode", sa.String(length=64), nullable=True))
        op.add_column("products", sa.Column("unit_of_measure", sa.String(length=20), nullable=False, server_default="pcs"))
        op.add_column("products", sa.Column("mrp", sa.Numeric(12, 2), nullable=True))
        op.add_column("products", sa.Column("brand", sa.String(length=120), nullable=True))
        op.add_column("products", sa.Column("manufacturer", sa.String(length=160), nullable=True))
        op.add_column("products", sa.Column("item_type", sa.String(length=20), nullable=False, server_default="goods"))
        op.add_column("products", sa.Column("batch_tracking_enabled", sa.Boolean(), nullable=False, server_default="false"))
        op.add_column("products", sa.Column("serial_tracking_enabled", sa.Boolean(), nullable=False, server_default="false"))
        op.add_column("products", sa.Column("expiry_tracking_enabled", sa.Boolean(), nullable=False, server_default="false"))
        op.create_index("ix_products_gst_rate_id", "products", ["gst_rate_id"])
        op.create_index("ix_products_primary_barcode", "products", ["primary_barcode"], unique=True)
    else:
        with op.batch_alter_table("products") as batch_op:
            batch_op.add_column(sa.Column("gst_rate_id", sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column("hsn_sac_code", sa.String(length=20), nullable=True))
            batch_op.add_column(sa.Column("cess_rate_percent", sa.Numeric(5, 2), nullable=False, server_default="0"))
            batch_op.add_column(sa.Column("primary_barcode", sa.String(length=64), nullable=True))
            batch_op.add_column(sa.Column("unit_of_measure", sa.String(length=20), nullable=False, server_default="pcs"))
            batch_op.add_column(sa.Column("mrp", sa.Numeric(12, 2), nullable=True))
            batch_op.add_column(sa.Column("brand", sa.String(length=120), nullable=True))
            batch_op.add_column(sa.Column("manufacturer", sa.String(length=160), nullable=True))
            batch_op.add_column(sa.Column("item_type", sa.String(length=20), nullable=False, server_default="goods"))
            batch_op.add_column(sa.Column("batch_tracking_enabled", sa.Boolean(), nullable=False, server_default="false"))
            batch_op.add_column(sa.Column("serial_tracking_enabled", sa.Boolean(), nullable=False, server_default="false"))
            batch_op.add_column(sa.Column("expiry_tracking_enabled", sa.Boolean(), nullable=False, server_default="false"))
            batch_op.create_foreign_key("fk_products_gst_rate_id_tax_rates", "tax_rates", ["gst_rate_id"], ["id"])
            batch_op.create_index("ix_products_gst_rate_id", ["gst_rate_id"])
            batch_op.create_index("ix_products_primary_barcode", ["primary_barcode"], unique=True)
            batch_op.create_check_constraint("ck_products_unit_cost_non_negative", "unit_cost >= 0")
            batch_op.create_check_constraint("ck_products_selling_price_non_negative", "selling_price >= 0")
            batch_op.create_check_constraint("ck_products_reorder_threshold_non_negative", "reorder_threshold >= 0")
            batch_op.create_check_constraint("ck_products_target_stock_non_negative", "target_stock_level >= 0")
            batch_op.create_check_constraint("ck_products_mrp_non_negative", "mrp IS NULL OR mrp >= 0")
            batch_op.create_check_constraint("ck_products_cess_non_negative", "cess_rate_percent >= 0")
            batch_op.create_check_constraint("ck_products_item_type", "item_type IN ('goods', 'service')")

    op.create_table(
        "product_barcodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("barcode", sa.String(length=64), nullable=False),
        sa.Column("barcode_type", sa.String(length=30), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("barcode"),
    )
    op.create_index("ix_product_barcodes_product_id", "product_barcodes", ["product_id"])
    op.create_index("ix_product_barcodes_barcode", "product_barcodes", ["barcode"])

    op.create_table(
        "product_units",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("symbol"),
    )

    op.create_table(
        "product_price_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("old_unit_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("new_unit_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("old_selling_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("new_selling_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("old_mrp", sa.Numeric(12, 2), nullable=True),
        sa.Column("new_mrp", sa.Numeric(12, 2), nullable=True),
        sa.Column("changed_by", sa.Integer(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.CheckConstraint("new_unit_cost >= 0", name="ck_product_price_history_unit_cost_non_negative"),
        sa.CheckConstraint("new_selling_price >= 0", name="ck_product_price_history_selling_price_non_negative"),
        sa.CheckConstraint("new_mrp IS NULL OR new_mrp >= 0", name="ck_product_price_history_mrp_non_negative"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_price_history_product_id", "product_price_history", ["product_id"])
    op.create_index("ix_product_price_history_changed_at", "product_price_history", ["changed_at"])

    op.create_table(
        "inventory_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("batch_number", sa.String(length=80), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("mrp", sa.Numeric(12, 2), nullable=True),
        sa.Column("quantity_on_hand", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity_on_hand >= 0", name="ck_inventory_batches_quantity_non_negative"),
        sa.CheckConstraint("mrp IS NULL OR mrp >= 0", name="ck_inventory_batches_mrp_non_negative"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "branch_id", "batch_number", name="uq_inventory_batches_product_branch_batch"),
    )
    op.create_index("ix_inventory_batches_product_id", "inventory_batches", ["product_id"])
    op.create_index("ix_inventory_batches_branch_id", "inventory_batches", ["branch_id"])
    op.create_index("ix_inventory_batches_expiry_date", "inventory_batches", ["expiry_date"])

    op.create_table(
        "serial_numbers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("serial_number", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("serial_number"),
    )
    op.create_index("ix_serial_numbers_product_id", "serial_numbers", ["product_id"])
    op.create_index("ix_serial_numbers_branch_id", "serial_numbers", ["branch_id"])
    op.create_index("ix_serial_numbers_status", "serial_numbers", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_serial_numbers_status", table_name="serial_numbers")
    op.drop_index("ix_serial_numbers_branch_id", table_name="serial_numbers")
    op.drop_index("ix_serial_numbers_product_id", table_name="serial_numbers")
    op.drop_table("serial_numbers")
    op.drop_index("ix_inventory_batches_expiry_date", table_name="inventory_batches")
    op.drop_index("ix_inventory_batches_branch_id", table_name="inventory_batches")
    op.drop_index("ix_inventory_batches_product_id", table_name="inventory_batches")
    op.drop_table("inventory_batches")
    op.drop_index("ix_product_price_history_changed_at", table_name="product_price_history")
    op.drop_index("ix_product_price_history_product_id", table_name="product_price_history")
    op.drop_table("product_price_history")
    op.drop_table("product_units")
    op.drop_index("ix_product_barcodes_barcode", table_name="product_barcodes")
    op.drop_index("ix_product_barcodes_product_id", table_name="product_barcodes")
    op.drop_table("product_barcodes")
    if bind.dialect.name == "sqlite":
        op.drop_index("ix_products_primary_barcode", table_name="products")
        op.drop_index("ix_products_gst_rate_id", table_name="products")
        op.drop_column("products", "expiry_tracking_enabled")
        op.drop_column("products", "serial_tracking_enabled")
        op.drop_column("products", "batch_tracking_enabled")
        op.drop_column("products", "item_type")
        op.drop_column("products", "manufacturer")
        op.drop_column("products", "brand")
        op.drop_column("products", "mrp")
        op.drop_column("products", "unit_of_measure")
        op.drop_column("products", "primary_barcode")
        op.drop_column("products", "cess_rate_percent")
        op.drop_column("products", "hsn_sac_code")
        op.drop_column("products", "gst_rate_id")
    else:
        with op.batch_alter_table("products") as batch_op:
            batch_op.drop_constraint("ck_products_item_type", type_="check")
            batch_op.drop_constraint("ck_products_cess_non_negative", type_="check")
            batch_op.drop_constraint("ck_products_mrp_non_negative", type_="check")
            batch_op.drop_constraint("ck_products_target_stock_non_negative", type_="check")
            batch_op.drop_constraint("ck_products_reorder_threshold_non_negative", type_="check")
            batch_op.drop_constraint("ck_products_selling_price_non_negative", type_="check")
            batch_op.drop_constraint("ck_products_unit_cost_non_negative", type_="check")
            batch_op.drop_index("ix_products_primary_barcode")
            batch_op.drop_index("ix_products_gst_rate_id")
            batch_op.drop_constraint("fk_products_gst_rate_id_tax_rates", type_="foreignkey")
            batch_op.drop_column("expiry_tracking_enabled")
            batch_op.drop_column("serial_tracking_enabled")
            batch_op.drop_column("batch_tracking_enabled")
            batch_op.drop_column("item_type")
            batch_op.drop_column("manufacturer")
            batch_op.drop_column("brand")
            batch_op.drop_column("mrp")
            batch_op.drop_column("unit_of_measure")
            batch_op.drop_column("primary_barcode")
            batch_op.drop_column("cess_rate_percent")
            batch_op.drop_column("hsn_sac_code")
            batch_op.drop_column("gst_rate_id")
