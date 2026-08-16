"""add public Cafe ordering foundation

Revision ID: 20260813_0012
Revises: 20260813_0011
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0012"
down_revision: str | None = "20260813_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("menu_categories", sa.Column("public_id", sa.String(64), nullable=True))
    op.add_column("menu_items", sa.Column("public_id", sa.String(64), nullable=True))
    op.add_column("table_sessions", sa.Column("bill_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE menu_categories SET public_id = replace(gen_random_uuid()::text, '-', '') WHERE public_id IS NULL")
    op.execute("UPDATE menu_items SET public_id = replace(gen_random_uuid()::text, '-', '') WHERE public_id IS NULL")
    op.alter_column("menu_categories", "public_id", nullable=False)
    op.alter_column("menu_items", "public_id", nullable=False)
    op.create_unique_constraint("uq_menu_categories_public_id", "menu_categories", ["public_id"])
    op.create_unique_constraint("uq_menu_items_public_id", "menu_items", ["public_id"])
    op.create_index("ix_menu_categories_public_id", "menu_categories", ["public_id"])
    op.create_index("ix_menu_items_public_id", "menu_items", ["public_id"])


def downgrade() -> None:
    op.drop_index("ix_menu_items_public_id", table_name="menu_items")
    op.drop_constraint("uq_menu_items_public_id", "menu_items", type_="unique")
    op.drop_index("ix_menu_categories_public_id", table_name="menu_categories")
    op.drop_constraint("uq_menu_categories_public_id", "menu_categories", type_="unique")
    op.drop_column("table_sessions", "bill_requested_at")
    op.drop_column("menu_items", "public_id")
    op.drop_column("menu_categories", "public_id")
