from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, delete, insert, select, update
from sqlalchemy.orm import Session

from app.api.errors import raise_bad_request, raise_conflict, raise_not_found
from app.cloud_db.schema import (
    inventory_availability_snapshots,
    published_menu_categories,
    published_menu_items,
    published_menu_versions,
    published_table_tokens,
)
from app.schemas.cloud import (
    MenuPublicationInput,
    MenuPublicationRead,
    SafeMenuCategoryRead,
    SafeMenuItemRead,
    SafeMenuRead,
)

INVALID_PUBLIC_REFERENCE = "Cafe access reference is invalid, expired, or disabled."


def publication_content_hash(payload: MenuPublicationInput) -> str:
    canonical = json.dumps(
        payload.model_dump(mode="json", exclude={"publication_id"}),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_publication(payload: MenuPublicationInput) -> None:
    category_ids = [row.source_category_id for row in payload.categories]
    if len(category_ids) != len(set(category_ids)):
        raise_bad_request("Publication contains duplicate category identifiers.")
    item_ids = [row.source_menu_item_id for row in payload.items]
    if len(item_ids) != len(set(item_ids)):
        raise_bad_request("Publication contains duplicate menu item identifiers.")
    table_ids = [row.source_table_id for row in payload.tables]
    if len(table_ids) != len(set(table_ids)):
        raise_bad_request("Publication contains duplicate table identifiers.")
    known_categories = set(category_ids)
    for item in payload.items:
        if item.source_category_id not in known_categories:
            raise_bad_request("Every published item must reference a category in the same publication.")


def _publication_row(db: Session, publication_id: UUID):
    return db.execute(
        select(published_menu_versions).where(
            published_menu_versions.c.publication_id == publication_id
        )
    ).mappings().first()


def publish_menu_snapshot(
    db: Session,
    *,
    payload: MenuPublicationInput,
    source_device_id: str,
) -> MenuPublicationRead:
    _validate_publication(payload)
    content_hash = publication_content_hash(payload)
    existing = _publication_row(db, payload.publication_id)
    if existing is not None:
        if existing["content_hash"] != content_hash:
            raise_conflict("This publication id was already used for different content.")
        return MenuPublicationRead(
            publication_id=existing["publication_id"],
            version=existing["version"],
            state=existing["state"],
            snapshot_at=existing["snapshot_at"],
            activated_at=existing["activated_at"],
            replayed=True,
        )

    version_collision = db.execute(
        select(published_menu_versions.c.id).where(
            published_menu_versions.c.company_id == payload.company_id,
            published_menu_versions.c.branch_id == payload.branch_id,
            published_menu_versions.c.version == payload.version,
        )
    ).first()
    if version_collision is not None:
        raise_conflict("This Cafe menu version already exists for the publication scope.")

    try:
        version_id = db.execute(
            insert(published_menu_versions)
            .values(
                publication_id=payload.publication_id,
                business_group_id=payload.business_group_id,
                company_id=payload.company_id,
                branch_id=payload.branch_id,
                version=payload.version,
                state="staging",
                content_hash=content_hash,
                source_device_id=source_device_id,
                category_count=len(payload.categories),
                item_count=len(payload.items),
                table_count=len(payload.tables),
                snapshot_at=payload.snapshot_at,
            )
            .returning(published_menu_versions.c.id)
        ).scalar_one()

        if payload.categories:
            db.execute(
                insert(published_menu_categories),
                [
                    {
                        "menu_version_id": version_id,
                        "source_category_id": row.source_category_id,
                        "name": row.name,
                        "display_order": row.display_order,
                        "is_active": row.is_active,
                    }
                    for row in payload.categories
                ],
            )
        if payload.items:
            db.execute(
                insert(published_menu_items),
                [
                    {
                        "menu_version_id": version_id,
                        "source_menu_item_id": row.source_menu_item_id,
                        "source_product_id": row.source_product_id,
                        "source_category_id": row.source_category_id,
                        "name": row.name,
                        "description": row.description,
                        "image_reference": row.image_reference,
                        "selling_price": row.selling_price,
                        "preparation_area": row.preparation_area,
                        "available": row.available,
                        "display_order": row.display_order,
                    }
                    for row in payload.items
                ],
            )
        if payload.tables:
            db.execute(
                insert(published_table_tokens),
                [
                    {
                        "menu_version_id": version_id,
                        "source_table_id": row.source_table_id,
                        "table_code": row.table_code,
                        "table_display_name": row.table_display_name,
                        "qr_public_reference": row.public_reference,
                        "qr_hash": row.verifier_digest,
                        "qr_expires_at": row.valid_until,
                        "revoked_at": row.disabled_at,
                        "available": row.available,
                    }
                    for row in payload.tables
                ],
            )
        if payload.availability:
            db.execute(
                insert(inventory_availability_snapshots),
                [
                    {
                        "business_group_id": payload.business_group_id,
                        "company_id": payload.company_id,
                        "branch_id": payload.branch_id,
                        "source_product_id": row.source_product_id,
                        "available": row.available,
                        "snapshot_at": payload.snapshot_at,
                        "source_device_id": source_device_id,
                    }
                    for row in payload.availability
                ],
            )

        activated_at = datetime.now(UTC)
        db.execute(
            update(published_menu_versions)
            .where(
                published_menu_versions.c.company_id == payload.company_id,
                published_menu_versions.c.branch_id == payload.branch_id,
                published_menu_versions.c.state == "active",
                published_menu_versions.c.id != version_id,
            )
            .values(state="superseded")
        )
        db.execute(
            update(published_menu_versions)
            .where(published_menu_versions.c.id == version_id)
            .values(state="active", activated_at=activated_at)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return MenuPublicationRead(
        publication_id=payload.publication_id,
        version=payload.version,
        state="active",
        snapshot_at=payload.snapshot_at,
        activated_at=activated_at,
    )


def get_safe_menu(db: Session, publication_id: UUID) -> SafeMenuRead:
    version = db.execute(
        select(published_menu_versions).where(
            published_menu_versions.c.publication_id == publication_id,
            published_menu_versions.c.state == "active",
        )
    ).mappings().first()
    if version is None:
        raise_not_found("Published Cafe menu is not available.")

    categories = db.execute(
        select(published_menu_categories)
        .where(
            published_menu_categories.c.menu_version_id == version["id"],
            published_menu_categories.c.is_active.is_(True),
        )
        .order_by(
            published_menu_categories.c.display_order,
            published_menu_categories.c.name,
        )
    ).mappings().all()
    items = db.execute(
        select(published_menu_items)
        .where(published_menu_items.c.menu_version_id == version["id"])
        .order_by(published_menu_items.c.display_order, published_menu_items.c.name)
    ).mappings().all()
    snapshot_at = version["snapshot_at"]
    if snapshot_at.tzinfo is None:
        snapshot_at = snapshot_at.replace(tzinfo=UTC)
    stale_age = max(0, int((datetime.now(UTC) - snapshot_at).total_seconds()))
    return SafeMenuRead(
        publication_id=version["publication_id"],
        version=version["version"],
        snapshot_at=snapshot_at,
        stale_age_seconds=stale_age,
        categories=[
            SafeMenuCategoryRead(
                source_category_id=row["source_category_id"],
                name=row["name"],
                display_order=row["display_order"],
            )
            for row in categories
        ],
        items=[
            SafeMenuItemRead(
                source_menu_item_id=row["source_menu_item_id"],
                source_category_id=row["source_category_id"],
                name=row["name"],
                description=row["description"],
                image_reference=row["image_reference"],
                selling_price=row["selling_price"],
                preparation_area=row["preparation_area"],
                available=row["available"],
                display_order=row["display_order"],
            )
            for row in items
        ],
    )


def resolve_published_table(db: Session, opaque_value: str) -> dict[str, object]:
    try:
        public_reference, proof = opaque_value.split(".", 1)
    except ValueError:
        raise_not_found(INVALID_PUBLIC_REFERENCE)
    if not public_reference or not proof:
        raise_not_found(INVALID_PUBLIC_REFERENCE)

    row = db.execute(
        select(
            published_table_tokens,
            published_menu_versions.c.publication_id,
            published_menu_versions.c.snapshot_at,
        ).join(
            published_menu_versions,
            published_menu_versions.c.id == published_table_tokens.c.menu_version_id,
        ).where(
            published_table_tokens.c.qr_public_reference == public_reference,
            published_menu_versions.c.state == "active",
        )
    ).mappings().first()
    if row is None or row["revoked_at"] is not None or not row["available"]:
        raise_not_found(INVALID_PUBLIC_REFERENCE)
    expires_at = row["qr_expires_at"]
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise_not_found(INVALID_PUBLIC_REFERENCE)
    candidate = hashlib.sha256(proof.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(candidate, row["qr_hash"]):
        raise_not_found(INVALID_PUBLIC_REFERENCE)
    snapshot_at = row["snapshot_at"]
    if snapshot_at.tzinfo is None:
        snapshot_at = snapshot_at.replace(tzinfo=UTC)
    return {
        "publication_id": row["publication_id"],
        "table_code": row["table_code"],
        "table_display_name": row["table_display_name"],
        "snapshot_at": snapshot_at,
        "stale_age_seconds": max(0, int((datetime.now(UTC) - snapshot_at).total_seconds())),
        "ordering_enabled": True,
    }
