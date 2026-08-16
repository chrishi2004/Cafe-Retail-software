from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.cloud_db.base import cloud_metadata

SCHEMA = "coordination"


def _uuid_column() -> sa.Column[uuid.UUID]:
    return sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _scope_columns() -> list[sa.Column]:
    return [
        sa.Column("business_group_id", sa.String(64), nullable=False),
        sa.Column("company_id", sa.String(64), nullable=True),
        sa.Column("branch_id", sa.String(64), nullable=True),
    ]


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


device_registrations = sa.Table(
    "device_registrations",
    cloud_metadata,
    _uuid_column(),
    sa.Column("device_id", sa.String(128), nullable=False, unique=True),
    *_scope_columns(),
    sa.Column("display_name", sa.String(160), nullable=False),
    sa.Column("credential_hash", sa.String(64), nullable=False),
    sa.Column("status", sa.String(24), nullable=False, server_default="active"),
    sa.Column("allowed_purposes", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('active','revoked','disabled')", name="ck_device_registration_status"),
    schema=SCHEMA,
)

device_heartbeats = sa.Table(
    "device_heartbeats",
    cloud_metadata,
    _uuid_column(),
    sa.Column("device_id", sa.String(128), nullable=False),
    *_scope_columns(),
    sa.Column("mode", sa.String(32), nullable=False),
    sa.Column("fencing_epoch", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("software_version", sa.String(64), nullable=True),
    sa.Column("event_schema_version", sa.Integer, nullable=False, server_default="1"),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.ForeignKeyConstraint(
        ["device_id"], [f"{SCHEMA}.device_registrations.device_id"], ondelete="CASCADE"
    ),
    schema=SCHEMA,
)

writer_leases = sa.Table(
    "writer_leases",
    cloud_metadata,
    _uuid_column(),
    sa.Column("scope_key", sa.String(256), nullable=False, unique=True),
    *_scope_columns(),
    sa.Column("current_mode", sa.String(32), nullable=False, server_default="local_writer"),
    sa.Column("lease_owner_device_id", sa.String(128), nullable=True),
    sa.Column("fencing_epoch", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("recovery_state", sa.String(32), nullable=False, server_default="healthy"),
    *_timestamps(),
    sa.CheckConstraint("fencing_epoch >= 0", name="ck_writer_lease_epoch_nonnegative"),
    schema=SCHEMA,
)

published_menu_versions = sa.Table(
    "published_menu_versions",
    cloud_metadata,
    _uuid_column(),
    sa.Column("publication_id", UUID(as_uuid=True), nullable=False, unique=True),
    *_scope_columns(),
    sa.Column("version", sa.BigInteger, nullable=False),
    sa.Column("state", sa.String(24), nullable=False, server_default="staging"),
    sa.Column("content_hash", sa.String(64), nullable=False),
    sa.Column("source_device_id", sa.String(128), nullable=False),
    sa.Column("category_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("item_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("table_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("version >= 1", name="ck_published_menu_version_positive"),
    sa.CheckConstraint("state IN ('staging','active','superseded','failed')", name="ck_published_menu_state"),
    sa.UniqueConstraint("company_id", "branch_id", "version", name="uq_published_menu_scope_version"),
    schema=SCHEMA,
)

published_menu_categories = sa.Table(
    "published_menu_categories",
    cloud_metadata,
    _uuid_column(),
    sa.Column("menu_version_id", UUID(as_uuid=True), nullable=False),
    sa.Column("source_category_id", sa.String(64), nullable=False),
    sa.Column("name", sa.String(120), nullable=False),
    sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.ForeignKeyConstraint(
        ["menu_version_id"], [f"{SCHEMA}.published_menu_versions.id"], ondelete="CASCADE"
    ),
    sa.UniqueConstraint("menu_version_id", "source_category_id", name="uq_pub_menu_category_source"),
    schema=SCHEMA,
)

published_menu_items = sa.Table(
    "published_menu_items",
    cloud_metadata,
    _uuid_column(),
    sa.Column("menu_version_id", UUID(as_uuid=True), nullable=False),
    sa.Column("source_menu_item_id", sa.String(64), nullable=False),
    sa.Column("source_product_id", sa.String(64), nullable=True),
    sa.Column("source_category_id", sa.String(64), nullable=False),
    sa.Column("name", sa.String(180), nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("image_reference", sa.String(500), nullable=True),
    sa.Column("selling_price", sa.Numeric(12, 2), nullable=False),
    sa.Column("preparation_area", sa.String(20), nullable=False),
    sa.Column("available", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
    sa.ForeignKeyConstraint(
        ["menu_version_id"], [f"{SCHEMA}.published_menu_versions.id"], ondelete="CASCADE"
    ),
    sa.UniqueConstraint("menu_version_id", "source_menu_item_id", name="uq_pub_menu_item_source"),
    sa.CheckConstraint("selling_price >= 0", name="ck_pub_menu_item_price_nonnegative"),
    schema=SCHEMA,
)

published_table_tokens = sa.Table(
    "published_table_tokens",
    cloud_metadata,
    _uuid_column(),
    sa.Column("menu_version_id", UUID(as_uuid=True), nullable=False),
    sa.Column("source_table_id", sa.String(64), nullable=False),
    sa.Column("table_code", sa.String(60), nullable=False),
    sa.Column("table_display_name", sa.String(120), nullable=False),
    sa.Column("qr_public_reference", sa.String(64), nullable=False),
    sa.Column("qr_hash", sa.String(64), nullable=False),
    sa.Column("qr_expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("available", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.ForeignKeyConstraint(
        ["menu_version_id"], [f"{SCHEMA}.published_menu_versions.id"], ondelete="CASCADE"
    ),
    sa.UniqueConstraint("menu_version_id", "source_table_id", name="uq_pub_table_source"),
    sa.UniqueConstraint("menu_version_id", "qr_public_reference", name="uq_pub_qr_reference_version"),
    schema=SCHEMA,
)

cloud_orders = sa.Table(
    "cloud_orders",
    cloud_metadata,
    _uuid_column(),
    sa.Column("public_id", UUID(as_uuid=True), nullable=False, unique=True),
    *_scope_columns(),
    sa.Column("table_public_reference", sa.String(64), nullable=True),
    sa.Column("status", sa.String(40), nullable=False, server_default="awaiting_cafe_confirmation"),
    sa.Column("idempotency_key_hash", sa.String(64), nullable=True),
    sa.Column("payload_hash", sa.String(64), nullable=True),
    sa.Column("customer_total", sa.Numeric(12, 2), nullable=True),
    *_timestamps(),
    schema=SCHEMA,
)

cloud_order_items = sa.Table(
    "cloud_order_items",
    cloud_metadata,
    _uuid_column(),
    sa.Column("order_id", UUID(as_uuid=True), nullable=False),
    sa.Column("source_menu_item_id", sa.String(64), nullable=False),
    sa.Column("name_snapshot", sa.String(180), nullable=False),
    sa.Column("unit_price_snapshot", sa.Numeric(12, 2), nullable=False),
    sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
    sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
    sa.ForeignKeyConstraint(["order_id"], [f"{SCHEMA}.cloud_orders.id"], ondelete="CASCADE"),
    schema=SCHEMA,
)

cloud_order_events = sa.Table(
    "cloud_order_events",
    cloud_metadata,
    _uuid_column(),
    sa.Column("event_id", UUID(as_uuid=True), nullable=False, unique=True),
    sa.Column("order_id", UUID(as_uuid=True), nullable=True),
    *_scope_columns(),
    sa.Column("event_type", sa.String(120), nullable=False),
    sa.Column("schema_version", sa.Integer, nullable=False, server_default="1"),
    sa.Column("aggregate_version", sa.BigInteger, nullable=False, server_default="1"),
    sa.Column("correlation_id", UUID(as_uuid=True), nullable=False),
    sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    schema=SCHEMA,
)

cloud_idempotency_keys = sa.Table(
    "cloud_idempotency_keys",
    cloud_metadata,
    _uuid_column(),
    *_scope_columns(),
    sa.Column("purpose", sa.String(80), nullable=False),
    sa.Column("key_hash", sa.String(64), nullable=False),
    sa.Column("request_hash", sa.String(64), nullable=False),
    sa.Column("result_reference", sa.String(128), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.UniqueConstraint("company_id", "branch_id", "purpose", "key_hash", name="uq_cloud_idempotency_scope_key"),
    schema=SCHEMA,
)

sync_commands = sa.Table(
    "sync_commands",
    cloud_metadata,
    _uuid_column(),
    sa.Column("event_id", UUID(as_uuid=True), nullable=False, unique=True),
    *_scope_columns(),
    sa.Column("target_device_id", sa.String(128), nullable=True),
    sa.Column("event_type", sa.String(120), nullable=False),
    sa.Column("schema_version", sa.Integer, nullable=False, server_default="1"),
    sa.Column("aggregate_type", sa.String(80), nullable=False),
    sa.Column("aggregate_id", sa.String(128), nullable=False),
    sa.Column("aggregate_version", sa.BigInteger, nullable=False),
    sa.Column("correlation_id", UUID(as_uuid=True), nullable=False),
    sa.Column("causation_id", UUID(as_uuid=True), nullable=True),
    sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    schema=SCHEMA,
)

sync_receipts = sa.Table(
    "sync_receipts",
    cloud_metadata,
    _uuid_column(),
    sa.Column("event_id", UUID(as_uuid=True), nullable=False, unique=True),
    sa.Column("device_id", sa.String(128), nullable=False),
    *_scope_columns(),
    sa.Column("status", sa.String(24), nullable=False),
    sa.Column("result_reference", sa.String(128), nullable=True),
    sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    schema=SCHEMA,
)

dashboard_snapshots = sa.Table(
    "dashboard_snapshots",
    cloud_metadata,
    _uuid_column(),
    *_scope_columns(),
    sa.Column("snapshot_type", sa.String(80), nullable=False),
    sa.Column("payload", JSONB, nullable=False),
    sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("source_device_id", sa.String(128), nullable=False),
    schema=SCHEMA,
)

inventory_availability_snapshots = sa.Table(
    "inventory_availability_snapshots",
    cloud_metadata,
    _uuid_column(),
    *_scope_columns(),
    sa.Column("source_product_id", sa.String(64), nullable=False),
    sa.Column("available", sa.Boolean, nullable=False),
    sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("source_device_id", sa.String(128), nullable=False),
    sa.UniqueConstraint("company_id", "branch_id", "source_product_id", "snapshot_at", name="uq_availability_snapshot"),
    schema=SCHEMA,
)

continuity_transactions = sa.Table(
    "continuity_transactions",
    cloud_metadata,
    _uuid_column(),
    sa.Column("continuity_reference", UUID(as_uuid=True), nullable=False, unique=True),
    *_scope_columns(),
    sa.Column("purpose", sa.String(80), nullable=False),
    sa.Column("fencing_epoch", sa.BigInteger, nullable=False),
    sa.Column("status", sa.String(32), nullable=False, server_default="pending_reconciliation"),
    sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    *_timestamps(),
    schema=SCHEMA,
)

cloud_tombstones = sa.Table(
    "cloud_tombstones",
    cloud_metadata,
    _uuid_column(),
    *_scope_columns(),
    sa.Column("aggregate_type", sa.String(80), nullable=False),
    sa.Column("aggregate_id", sa.String(128), nullable=False),
    sa.Column("aggregate_version", sa.BigInteger, nullable=False),
    sa.Column("reason", sa.String(240), nullable=True),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.UniqueConstraint("company_id", "branch_id", "aggregate_type", "aggregate_id", "aggregate_version", name="uq_cloud_tombstone_version"),
    schema=SCHEMA,
)

for table, columns in (
    (device_registrations, ("business_group_id", "company_id", "branch_id")),
    (device_heartbeats, ("device_id", "recorded_at")),
    (published_menu_versions, ("company_id", "branch_id", "state", "version")),
    (published_menu_items, ("menu_version_id", "available")),
    (published_table_tokens, ("menu_version_id", "qr_public_reference")),
    (cloud_orders, ("company_id", "branch_id", "status", "created_at")),
    (sync_commands, ("target_device_id", "status", "recorded_at")),
    (dashboard_snapshots, ("company_id", "branch_id", "snapshot_at")),
    (inventory_availability_snapshots, ("company_id", "branch_id", "snapshot_at")),
):
    sa.Index(f"ix_{table.name}_{'_'.join(columns)}", *(table.c[name] for name in columns))
