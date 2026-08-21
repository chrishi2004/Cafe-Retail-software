"""add durable cloud bill request aggregate

Revision ID: 20260821_cloud_0003
Revises: 20260814_cloud_0002
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260821_cloud_0003"
down_revision: str | None = "20260814_cloud_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cloud_bill_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("public_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("order_public_id", UUID(as_uuid=True), nullable=False),
        sa.Column("business_group_id", sa.String(length=64), nullable=False),
        sa.Column("company_id", sa.String(length=64), nullable=False),
        sa.Column("branch_id", sa.String(length=64), nullable=False),
        sa.Column("table_public_reference", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "branch_id", "idempotency_key_hash", name="uq_cloud_bill_request_key"),
        sa.CheckConstraint("status IN ('queued','acknowledged','rejected')", name="ck_cloud_bill_request_status"),
        schema="coordination",
    )
    op.create_index(
        "ix_cloud_bill_requests_order_public_id",
        "cloud_bill_requests",
        ["order_public_id"],
        schema="coordination",
    )
    op.execute("ALTER TABLE coordination.cloud_bill_requests ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    # Coordination commands are durable evidence. Destructive cloud downgrade
    # remains an explicit operator action rather than silently deleting them.
    pass
