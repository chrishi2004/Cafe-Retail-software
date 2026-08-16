from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Header, Request
from sqlalchemy import insert, select, update

from app.api.errors import raise_conflict, raise_not_found
from app.api.routes.cloud_gateway import (
    Database,
    _active_device,
    _require_scope_values,
    _verify_signed_request,
)
from app.cloud_db.schema import continuity_transactions, sync_commands, writer_leases
from app.schemas.hc4 import ContinuityReferenceInput, ContinuityReferenceRead, WriterLeaseInput, WriterLeaseRead

router = APIRouter(prefix="/cloud/continuity", tags=["hc4-continuity"])


def _headers(
    x_device_id: Annotated[str, Header(alias="X-Device-Id")],
    x_device_proof: Annotated[str, Header(alias="X-Device-Proof")],
    x_device_timestamp: Annotated[str, Header(alias="X-Device-Timestamp")],
    x_device_nonce: Annotated[str, Header(alias="X-Device-Nonce")],
    x_device_signature: Annotated[str, Header(alias="X-Device-Signature")],
):
    return x_device_id, x_device_proof, x_device_timestamp, x_device_nonce, x_device_signature


def _lease_read(row) -> WriterLeaseRead:
    return WriterLeaseRead(
        scope_key=row["scope_key"],
        current_mode=row["current_mode"],
        lease_owner_device_id=row["lease_owner_device_id"],
        fencing_epoch=int(row["fencing_epoch"]),
        lease_expires_at=row["lease_expires_at"],
        last_heartbeat_at=row["last_heartbeat_at"],
        recovery_state=row["recovery_state"],
    )


def _authorize_signed(
    db: Database,
    *,
    payload: object,
    device_id: str,
    proof: str,
    timestamp: str,
    nonce: str,
    signature: str,
):
    device = _active_device(db, device_id=device_id, proof=proof, purpose="heartbeat")
    _verify_signed_request(
        db,
        device=device,
        device_id=device_id,
        timestamp=timestamp,
        nonce=nonce,
        signature=signature,
        payload=payload,
    )
    return device


@router.post("/lease/acquire", response_model=WriterLeaseRead)
def acquire_writer_lease(
    payload: WriterLeaseInput,
    request: Request,
    db: Database,
    x_device_id: Annotated[str, Header(alias="X-Device-Id")],
    x_device_proof: Annotated[str, Header(alias="X-Device-Proof")],
    x_device_timestamp: Annotated[str, Header(alias="X-Device-Timestamp")],
    x_device_nonce: Annotated[str, Header(alias="X-Device-Nonce")],
    x_device_signature: Annotated[str, Header(alias="X-Device-Signature")],
) -> WriterLeaseRead:
    device = _authorize_signed(
        db,
        payload=payload,
        device_id=x_device_id,
        proof=x_device_proof,
        timestamp=x_device_timestamp,
        nonce=x_device_nonce,
        signature=x_device_signature,
    )
    _require_scope_values(
        device,
        business_group_id=payload.business_group_id,
        company_id=payload.company_id,
        branch_id=payload.branch_id,
    )
    now = datetime.now(UTC)
    lease_seconds = request.app.state.settings.writer_lease_seconds
    row = db.execute(
        select(writer_leases).where(writer_leases.c.scope_key == payload.scope_key).with_for_update()
    ).mappings().first()
    if row is None:
        epoch = 1
        db.execute(
            insert(writer_leases).values(
                scope_key=payload.scope_key,
                business_group_id=payload.business_group_id,
                company_id=payload.company_id,
                branch_id=payload.branch_id,
                current_mode=payload.requested_mode,
                lease_owner_device_id=x_device_id,
                fencing_epoch=epoch,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                last_heartbeat_at=now,
                recovery_state="recovering" if payload.requested_mode == "recovering" else "healthy",
            )
        )
    else:
        _require_scope_values(
            device,
            business_group_id=str(row["business_group_id"]),
            company_id=str(row["company_id"]) if row["company_id"] is not None else None,
            branch_id=str(row["branch_id"]) if row["branch_id"] is not None else None,
        )
        active = row["lease_expires_at"] is not None and row["lease_expires_at"] > now
        if active and row["lease_owner_device_id"] not in {None, x_device_id}:
            raise_conflict("Writer lease is held by another active device.")
        if active and row["lease_owner_device_id"] == x_device_id:
            if payload.fencing_epoch is not None and payload.fencing_epoch != int(row["fencing_epoch"]):
                raise_conflict("Writer lease fencing epoch is stale.")
            epoch = int(row["fencing_epoch"])
        else:
            epoch = int(row["fencing_epoch"]) + 1
        db.execute(
            update(writer_leases)
            .where(writer_leases.c.id == row["id"])
            .values(
                current_mode=payload.requested_mode,
                lease_owner_device_id=x_device_id,
                fencing_epoch=epoch,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                last_heartbeat_at=now,
                recovery_state="recovering" if payload.requested_mode == "recovering" else "healthy",
                updated_at=now,
            )
        )
    db.commit()
    current = db.execute(
        select(writer_leases).where(writer_leases.c.scope_key == payload.scope_key)
    ).mappings().one()
    return _lease_read(current)


@router.post("/lease/renew", response_model=WriterLeaseRead)
def renew_writer_lease(
    payload: WriterLeaseInput,
    request: Request,
    db: Database,
    x_device_id: Annotated[str, Header(alias="X-Device-Id")],
    x_device_proof: Annotated[str, Header(alias="X-Device-Proof")],
    x_device_timestamp: Annotated[str, Header(alias="X-Device-Timestamp")],
    x_device_nonce: Annotated[str, Header(alias="X-Device-Nonce")],
    x_device_signature: Annotated[str, Header(alias="X-Device-Signature")],
) -> WriterLeaseRead:
    device = _authorize_signed(
        db,
        payload=payload,
        device_id=x_device_id,
        proof=x_device_proof,
        timestamp=x_device_timestamp,
        nonce=x_device_nonce,
        signature=x_device_signature,
    )
    _require_scope_values(
        device,
        business_group_id=payload.business_group_id,
        company_id=payload.company_id,
        branch_id=payload.branch_id,
    )
    now = datetime.now(UTC)
    row = db.execute(
        select(writer_leases).where(writer_leases.c.scope_key == payload.scope_key).with_for_update()
    ).mappings().first()
    if row is None:
        raise_not_found("Writer lease does not exist.")
    if row["lease_owner_device_id"] != x_device_id:
        raise_conflict("Writer lease is owned by another device.")
    if row["lease_expires_at"] is None or row["lease_expires_at"] <= now:
        raise_conflict("Writer lease expired; acquire a new fenced epoch.")
    if payload.fencing_epoch is None or payload.fencing_epoch != int(row["fencing_epoch"]):
        raise_conflict("Writer lease fencing epoch is stale.")
    db.execute(
        update(writer_leases)
        .where(writer_leases.c.id == row["id"])
        .values(
            current_mode=payload.requested_mode,
            lease_expires_at=now + timedelta(seconds=request.app.state.settings.writer_lease_seconds),
            last_heartbeat_at=now,
            recovery_state="recovering" if payload.requested_mode == "recovering" else "healthy",
            updated_at=now,
        )
    )
    db.commit()
    current = db.execute(
        select(writer_leases).where(writer_leases.c.scope_key == payload.scope_key)
    ).mappings().one()
    return _lease_read(current)


@router.post("/references", response_model=ContinuityReferenceRead, status_code=201)
def create_continuity_reference(
    payload: ContinuityReferenceInput,
    db: Database,
    x_device_id: Annotated[str, Header(alias="X-Device-Id")],
    x_device_proof: Annotated[str, Header(alias="X-Device-Proof")],
    x_device_timestamp: Annotated[str, Header(alias="X-Device-Timestamp")],
    x_device_nonce: Annotated[str, Header(alias="X-Device-Nonce")],
    x_device_signature: Annotated[str, Header(alias="X-Device-Signature")],
) -> ContinuityReferenceRead:
    device = _authorize_signed(
        db,
        payload=payload,
        device_id=x_device_id,
        proof=x_device_proof,
        timestamp=x_device_timestamp,
        nonce=x_device_nonce,
        signature=x_device_signature,
    )
    _require_scope_values(
        device,
        business_group_id=payload.business_group_id,
        company_id=payload.company_id,
        branch_id=payload.branch_id,
    )
    lease = db.execute(
        select(writer_leases).where(writer_leases.c.scope_key == payload.scope_key)
    ).mappings().first()
    if lease is None or int(lease["fencing_epoch"]) != payload.fencing_epoch:
        raise_conflict("Continuity reference fencing epoch is stale or unknown.")

    existing = db.execute(
        select(continuity_transactions).where(
            continuity_transactions.c.continuity_reference == payload.continuity_reference
        )
    ).mappings().first()
    canonical = json.dumps(payload.payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if existing is not None:
        existing_digest = hashlib.sha256(
            json.dumps(existing["payload"] or {}, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()
        if existing_digest != digest or int(existing["fencing_epoch"]) != payload.fencing_epoch:
            raise_conflict("Continuity reference was reused with different content.")
        return ContinuityReferenceRead(
            continuity_reference=payload.continuity_reference,
            status=existing["status"],
            fencing_epoch=int(existing["fencing_epoch"]),
            replayed=True,
        )

    db.execute(
        insert(continuity_transactions).values(
            continuity_reference=payload.continuity_reference,
            business_group_id=payload.business_group_id,
            company_id=payload.company_id,
            branch_id=payload.branch_id,
            purpose=payload.purpose,
            fencing_epoch=payload.fencing_epoch,
            status="pending_reconciliation",
            payload=payload.payload,
        )
    )
    event_id = uuid4()
    correlation_id = uuid4()
    db.execute(
        insert(sync_commands).values(
            event_id=event_id,
            business_group_id=payload.business_group_id,
            company_id=payload.company_id,
            branch_id=payload.branch_id,
            target_device_id=None,
            event_type="continuity.reference.created",
            schema_version=1,
            aggregate_type="continuity_transaction",
            aggregate_id=str(payload.continuity_reference),
            aggregate_version=1,
            correlation_id=correlation_id,
            payload={
                "continuity_reference": str(payload.continuity_reference),
                "scope_key": payload.scope_key,
                "purpose": payload.purpose,
                "fencing_epoch": payload.fencing_epoch,
                "payload": payload.payload,
            },
            status="pending",
        )
    )
    db.commit()
    return ContinuityReferenceRead(
        continuity_reference=payload.continuity_reference,
        status="pending_reconciliation",
        fencing_epoch=payload.fencing_epoch,
        replayed=False,
    )
