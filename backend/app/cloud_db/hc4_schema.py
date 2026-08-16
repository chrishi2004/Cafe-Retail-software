from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from app.cloud_db.base import cloud_metadata
from app.cloud_db.schema import SCHEMA


continuity_request_nonces = sa.Table(
    "continuity_request_nonces",
    cloud_metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    sa.Column("device_id", sa.String(128), nullable=False),
    sa.Column("request_nonce", sa.String(64), nullable=False),
    sa.Column("signature_timestamp", sa.DateTime(timezone=True), nullable=False),
    sa.Column("request_digest", sa.String(64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(
        ["device_id"], [f"{SCHEMA}.device_registrations.device_id"], ondelete="CASCADE"
    ),
    sa.UniqueConstraint("device_id", "request_nonce", name="uq_continuity_request_nonce_device"),
    schema=SCHEMA,
)

sa.Index(
    "ix_continuity_request_nonces_expires_at",
    continuity_request_nonces.c.expires_at,
)
