"""add durable cloud/local record links

Revision ID: 20260814_0014
Revises: 20260813_0013
Create Date: 2026-08-14
"""

from collections.abc import Sequence

from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision: str = "20260814_0014"
down_revision: str | None = "20260813_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.tables["cloud_record_links"].create(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    op.drop_table("cloud_record_links")
