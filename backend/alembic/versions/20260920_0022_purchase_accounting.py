"""Phase 9 purchase bills, supplier ledger, payments and debit notes.

Revision ID: 20260920_0022
Revises: 20260920_0021
"""

from alembic import op
import sqlalchemy as sa

revision = "20260920_0022"
down_revision = "20260920_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("purchase_bills",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, server_default="1"),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False), sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("bill_number", sa.String(80), nullable=False), sa.Column("supplier_invoice_number", sa.String(120)), sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="issued"), sa.Column("total_amount", sa.Numeric(14, 2), nullable=False), sa.Column("paid_amount", sa.Numeric(14, 2), nullable=False, server_default="0"), sa.Column("balance_due", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("idempotency_key", sa.String(128), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "bill_number", name="uq_purchase_bills_company_number"), sa.UniqueConstraint("company_id", "idempotency_key", name="uq_purchase_bills_company_idempotency"))
    op.create_index("ix_purchase_bills_company_id", "purchase_bills", ["company_id"]); op.create_index("ix_purchase_bills_supplier_id", "purchase_bills", ["supplier_id"]); op.create_index("ix_purchase_bills_branch_id", "purchase_bills", ["branch_id"])
    op.create_table("purchase_bill_items",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("bill_id", sa.Integer(), sa.ForeignKey("purchase_bills.id", ondelete="CASCADE"), nullable=False), sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False), sa.Column("quantity", sa.Numeric(12, 2), nullable=False), sa.Column("unit_cost", sa.Numeric(14, 2), nullable=False), sa.Column("line_total", sa.Numeric(14, 2), nullable=False))
    op.create_index("ix_purchase_bill_items_bill_id", "purchase_bill_items", ["bill_id"])
    op.create_table("supplier_ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, server_default="1"), sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False), sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False), sa.Column("entry_type", sa.String(32), nullable=False), sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default="0"), sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default="0"), sa.Column("reference_type", sa.String(80)), sa.Column("reference_id", sa.Integer()), sa.Column("reason", sa.Text(), nullable=False), sa.Column("idempotency_key", sa.String(128), nullable=False), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("entry_datetime", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("company_id", "idempotency_key", name="uq_supplier_ledger_company_idempotency"))
    op.create_index("ix_supplier_ledger_company_supplier", "supplier_ledger_entries", ["company_id", "supplier_id"])
    op.create_table("purchase_debit_notes",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, server_default="1"), sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False), sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False), sa.Column("bill_id", sa.Integer(), sa.ForeignKey("purchase_bills.id")), sa.Column("debit_note_number", sa.String(80), nullable=False), sa.Column("amount", sa.Numeric(14, 2), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("idempotency_key", sa.String(128), nullable=False), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("company_id", "debit_note_number", name="uq_purchase_debit_notes_company_number"), sa.UniqueConstraint("company_id", "idempotency_key", name="uq_purchase_debit_notes_company_idempotency"))
    op.create_index("ix_purchase_debit_notes_supplier_id", "purchase_debit_notes", ["supplier_id"])


def downgrade() -> None:
    op.drop_index("ix_purchase_debit_notes_supplier_id", table_name="purchase_debit_notes"); op.drop_table("purchase_debit_notes")
    op.drop_index("ix_supplier_ledger_company_supplier", table_name="supplier_ledger_entries"); op.drop_table("supplier_ledger_entries")
    op.drop_index("ix_purchase_bill_items_bill_id", table_name="purchase_bill_items"); op.drop_table("purchase_bill_items")
    op.drop_index("ix_purchase_bills_branch_id", table_name="purchase_bills"); op.drop_index("ix_purchase_bills_supplier_id", table_name="purchase_bills"); op.drop_index("ix_purchase_bills_company_id", table_name="purchase_bills"); op.drop_table("purchase_bills")
