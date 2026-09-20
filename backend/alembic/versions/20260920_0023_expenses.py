"""Phase 10 expense categories, entries and cashbook summaries.

Revision ID: 20260920_0023
Revises: 20260920_0022
"""

from alembic import op
import sqlalchemy as sa

revision = "20260920_0023"
down_revision = "20260920_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("expense_categories", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, server_default="1"), sa.Column("name", sa.String(100), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("company_id", "name", name="uq_expense_categories_company_name"))
    op.create_index("ix_expense_categories_company_id", "expense_categories", ["company_id"])
    op.create_table("expense_entries", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, server_default="1"), sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False), sa.Column("category_id", sa.Integer(), sa.ForeignKey("expense_categories.id"), nullable=False), sa.Column("expense_date", sa.Date(), nullable=False), sa.Column("amount", sa.Numeric(14, 2), nullable=False), sa.Column("payment_mode", sa.String(40), nullable=False, server_default="cash"), sa.Column("vendor_name", sa.String(180)), sa.Column("reason", sa.Text(), nullable=False), sa.Column("idempotency_key", sa.String(128), nullable=False), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("company_id", "idempotency_key", name="uq_expense_entries_company_idempotency"))
    op.create_index("ix_expense_entries_company_branch_date", "expense_entries", ["company_id", "branch_id", "expense_date"])
    op.create_index("ix_expense_entries_category_id", "expense_entries", ["category_id"])


def downgrade() -> None:
    op.drop_index("ix_expense_entries_category_id", table_name="expense_entries"); op.drop_index("ix_expense_entries_company_branch_date", table_name="expense_entries"); op.drop_table("expense_entries")
    op.drop_index("ix_expense_categories_company_id", table_name="expense_categories"); op.drop_table("expense_categories")
