from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from app.cloud_db.base import cloud_metadata
from app.cloud_db.schema import SCHEMA


cloud_bill_requests = sa.Table(
    "cloud_bill_requests",
    cloud_metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    sa.Column("public_id", UUID(as_uuid=True), nullable=False, unique=True),
    sa.Column("order_public_id", UUID(as_uuid=True), nullable=False),
    sa.Column("business_group_id", sa.String(64), nullable=False),
    sa.Column("company_id", sa.String(64), nullable=False),
    sa.Column("branch_id", sa.String(64), nullable=False),
    sa.Column("table_public_reference", sa.String(64), nullable=False),
    sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
    sa.Column("request_hash", sa.String(64), nullable=False),
    sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
    sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.UniqueConstraint("company_id", "branch_id", "idempotency_key_hash", name="uq_cloud_bill_request_key"),
    sa.CheckConstraint("status IN ('queued','acknowledged','rejected')", name="ck_cloud_bill_request_status"),
    schema=SCHEMA,
)
