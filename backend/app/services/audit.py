from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.db.scoping import current_scope
from app.models import AuditLog, User


def get_request_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host


def write_audit_log(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    user: User | None = None,
    user_id: int | None = None,
    company_id: int | None = None,
    old_value_json: dict[str, Any] | None = None,
    new_value_json: dict[str, Any] | None = None,
    request: Request | None = None,
    ip_address: str | None = None,
    notes: str | None = None,
    commit: bool = False,
) -> AuditLog:
    scope = current_scope(db)
    resolved_company_id = company_id
    if resolved_company_id is None and user is not None:
        resolved_company_id = user.company_id
    if resolved_company_id is None and scope is not None:
        resolved_company_id = scope.company_id

    audit_kwargs: dict[str, Any] = {
        "user_id": user.id if user is not None else user_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "old_value_json": old_value_json,
        "new_value_json": new_value_json,
        "ip_address": ip_address or get_request_ip(request),
        "notes": notes,
    }
    # Pre-authentication/global-owner audit events retain the P1 legacy default
    # rather than inventing a company. Company-scoped requests always resolve one.
    if resolved_company_id is not None:
        audit_kwargs["company_id"] = resolved_company_id

    audit_log = AuditLog(**audit_kwargs)
    db.add(audit_log)

    if commit:
        db.commit()
        db.refresh(audit_log)
    else:
        db.flush()

    return audit_log
