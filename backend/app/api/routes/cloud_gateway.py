from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.errors import raise_conflict, raise_forbidden, raise_unauthorized
from app.cloud_db.hc4_schema import continuity_request_nonces
from app.cloud_db.schema import device_heartbeats, device_registrations, writer_leases
from app.db.session import get_db
from app.schemas.cloud import MenuPublicationInput, MenuPublicationRead, SafeMenuRead
from app.schemas.hc4 import SignedHeartbeatInput, SignedHeartbeatRead, WriterLeaseRead
from app.services.cloud_coordination import get_safe_menu, publish_menu_snapshot, resolve_published_table

router = APIRouter(prefix="/cloud", tags=["cloud-gateway"])
Database = Annotated[Session, Depends(get_db)]


def cloud_readiness_snapshot(settings, *, database_ready: bool) -> dict[str, object]:
    """Return safe deployment diagnostics without exposing connection secrets."""
    required_checks = {
        "runtime_database_configured": bool(settings.cloud_runtime_database_url),
        "migration_database_configured": bool(settings.cloud_migration_database_url),
    }
    recommended_checks = {
        "gateway_url_configured": bool(settings.cloud_gateway_base_url),
        "sync_device_id_configured": bool(settings.sync_device_id),
        "sync_device_secret_configured": settings.sync_device_secret is not None,
    }
    if not database_ready:
        status = "not_ready"
    elif not all(required_checks.values()):
        status = "configuration_required"
    else:
        status = "ready"
    return {
        "status": status,
        "deployment_mode": settings.deployment_mode.value,
        "database_ready": database_ready,
        "cloud_schema_revision": "20260814_cloud_0002",
        "checks": {
            "required": required_checks,
            "recommended": recommended_checks,
        },
    }


def _active_device(db: Session, *, device_id: str, proof: str, purpose: str):
    row = db.execute(select(device_registrations).where(device_registrations.c.device_id == device_id)).mappings().first()
    if row is None or row["status"] != "active" or row["revoked_at"] is not None:
        raise_unauthorized("Device authorization is not active.")
    candidate = hashlib.sha256(proof.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(candidate, row["credential_hash"]):
        raise_unauthorized("Device authorization is not active.")
    if purpose not in (row["allowed_purposes"] or []):
        raise_forbidden("Device is not authorized for this operation.")
    return row


def _require_scope_values(row, *, business_group_id: str, company_id: str | None, branch_id: str | None) -> None:
    if str(row["business_group_id"]) != str(business_group_id):
        raise_forbidden("Operation scope is not authorized for this device.")
    if row["company_id"] is not None and str(row["company_id"]) != str(company_id):
        raise_forbidden("Operation scope is not authorized for this device.")
    if row["branch_id"] is not None and str(row["branch_id"]) != str(branch_id):
        raise_forbidden("Operation scope is not authorized for this device.")


def _require_scope(row, payload: MenuPublicationInput) -> None:
    _require_scope_values(row, business_group_id=payload.business_group_id, company_id=payload.company_id, branch_id=payload.branch_id)


def _canonical_payload_digest(payload: object) -> str:
    value = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _verify_signed_request(
    db: Session,
    *,
    device,
    device_id: str,
    timestamp: str,
    nonce: str,
    signature: str,
    payload: object,
    max_skew_seconds: int = 300,
) -> None:
    try:
        timestamp_seconds = int(timestamp)
    except ValueError:
        raise_unauthorized("Device request signature is invalid.")
    signed_at = datetime.fromtimestamp(timestamp_seconds, tz=UTC)
    now = datetime.now(UTC)
    if abs((now - signed_at).total_seconds()) > max_skew_seconds:
        raise_unauthorized("Device request signature is stale.")
    if not nonce or len(nonce) > 64:
        raise_unauthorized("Device request nonce is invalid.")
    digest = _canonical_payload_digest(payload)
    canonical = f"{device_id}\n{timestamp}\n{nonce}\n{digest}".encode("utf-8")
    expected = hmac.new(str(device["credential_hash"]).encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise_unauthorized("Device request signature is invalid.")
    db.execute(delete(continuity_request_nonces).where(continuity_request_nonces.c.expires_at < now))
    try:
        with db.begin_nested():
            db.execute(
                insert(continuity_request_nonces).values(
                    device_id=device_id,
                    request_nonce=nonce,
                    signature_timestamp=signed_at,
                    request_digest=digest,
                    expires_at=now + timedelta(seconds=max_skew_seconds * 2),
                )
            )
    except IntegrityError:
        raise_conflict("Device request nonce was already used.")


def _lease_read(row) -> WriterLeaseRead | None:
    if row is None:
        return None
    return WriterLeaseRead(
        scope_key=row["scope_key"],
        current_mode=row["current_mode"],
        lease_owner_device_id=row["lease_owner_device_id"],
        fencing_epoch=int(row["fencing_epoch"]),
        lease_expires_at=row["lease_expires_at"],
        last_heartbeat_at=row["last_heartbeat_at"],
        recovery_state=row["recovery_state"],
    )


@router.get("/readiness")
def readiness(db: Database, request: Request) -> dict[str, object]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return cloud_readiness_snapshot(request.app.state.settings, database_ready=False)
    return cloud_readiness_snapshot(request.app.state.settings, database_ready=True)


@router.post("/devices/heartbeat", response_model=SignedHeartbeatRead)
def heartbeat(
    payload: SignedHeartbeatInput,
    db: Database,
    x_device_id: Annotated[str, Header(alias="X-Device-Id")],
    x_device_proof: Annotated[str, Header(alias="X-Device-Proof")],
    x_device_timestamp: Annotated[str | None, Header(alias="X-Device-Timestamp")] = None,
    x_device_nonce: Annotated[str | None, Header(alias="X-Device-Nonce")] = None,
    x_device_signature: Annotated[str | None, Header(alias="X-Device-Signature")] = None,
) -> SignedHeartbeatRead:
    # Authenticate/revocation-check before signature-header validation so a
    # revoked device still fails as unauthorized rather than as request-shape 422.
    device = _active_device(db, device_id=x_device_id, proof=x_device_proof, purpose="heartbeat")
    if not x_device_timestamp or not x_device_nonce or not x_device_signature:
        raise_unauthorized("Signed heartbeat headers are required.")
    _verify_signed_request(
        db,
        device=device,
        device_id=x_device_id,
        timestamp=x_device_timestamp,
        nonce=x_device_nonce,
        signature=x_device_signature,
        payload=payload,
    )
    now = datetime.now(UTC)
    db.execute(
        insert(device_heartbeats).values(
            device_id=device["device_id"],
            business_group_id=device["business_group_id"],
            company_id=device["company_id"],
            branch_id=device["branch_id"],
            mode=payload.mode,
            fencing_epoch=payload.fencing_epoch,
            software_version=payload.software_version,
            event_schema_version=payload.event_schema_version,
            recorded_at=now,
        )
    )
    db.execute(update(device_registrations).where(device_registrations.c.device_id == device["device_id"]).values(last_seen_at=now))
    lease = db.execute(
        select(writer_leases).where(writer_leases.c.lease_owner_device_id == x_device_id)
        .order_by(writer_leases.c.updated_at.desc()).limit(1)
    ).mappings().first()
    if lease is not None and payload.fencing_epoch not in {0, int(lease["fencing_epoch"])}:
        raise_conflict("Heartbeat fencing epoch is stale.")
    if lease is not None:
        db.execute(update(writer_leases).where(writer_leases.c.id == lease["id"]).values(last_heartbeat_at=now))
        lease = dict(lease)
        lease["last_heartbeat_at"] = now
    db.commit()
    return SignedHeartbeatRead(
        accepted=True,
        device_id=device["device_id"],
        recorded_at=now,
        business_group_id=str(device["business_group_id"]),
        company_id=str(device["company_id"]) if device["company_id"] is not None else None,
        branch_id=str(device["branch_id"]) if device["branch_id"] is not None else None,
        lease=_lease_read(lease),
    )


@router.post("/publications/menu", response_model=MenuPublicationRead)
def publish_menu(
    payload: MenuPublicationInput,
    db: Database,
    x_device_id: Annotated[str, Header(alias="X-Device-Id")],
    x_device_proof: Annotated[str, Header(alias="X-Device-Proof")],
) -> MenuPublicationRead:
    device = _active_device(db, device_id=x_device_id, proof=x_device_proof, purpose="menu_publication")
    _require_scope(device, payload)
    return publish_menu_snapshot(db, payload=payload, source_device_id=device["device_id"])


@router.get("/public/cafe/menu/{publication_id}", response_model=SafeMenuRead)
def public_menu(publication_id: UUID, db: Database) -> SafeMenuRead:
    return get_safe_menu(db, publication_id)


@router.post("/public/cafe/qr/resolve")
def public_qr_resolve(payload: dict[str, str], db: Database) -> dict[str, object]:
    return resolve_published_table(db, str(payload.get("opaque_token", "")))
