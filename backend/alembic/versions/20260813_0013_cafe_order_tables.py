"""create Cafe ordering tables

Revision ID: 20260813_0013
Revises: 20260813_0012
Create Date: 2026-08-13
"""

from collections.abc import Sequence

from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision: str = "20260813_0013"
down_revision: str | None = "20260813_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "cafe_guest_access",
    "cafe_orders",
    "cafe_order_items",
    "cafe_order_status_history",
    "public_rate_limit_buckets",
)


def upgrade() -> None:
    bind = op.get_bind()
    for name in TABLES:
        Base.metadata.tables[name].create(bind=bind, checkfirst=False)


def downgrade() -> None:
    for name in reversed(TABLES):
        op.drop_table(name)
