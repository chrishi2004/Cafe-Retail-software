from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import TableSession, TableSessionStatus, TableSessionType
from app.schemas.public_cafe import PublicQrResolveRead
from app.services.cafe import _resolve_qr_record
from app.services.public_cafe import resolve_qr_for_guest


def resolve_qr_and_open_visit(db: Session, *, raw_qr: str) -> PublicQrResolveRead:
    _qr, table, company = _resolve_qr_record(db, raw_qr, update_last_used=False)
    session = db.scalar(
        select(TableSession)
        .where(
            TableSession.table_id == table.id,
            TableSession.company_id == company.id,
            TableSession.branch_id == table.branch_id,
            TableSession.status.in_(
                [
                    TableSessionStatus.OPEN,
                    TableSessionStatus.BILL_REQUESTED,
                    TableSessionStatus.BILLED,
                ]
            ),
        )
        .order_by(TableSession.opened_at.desc(), TableSession.id.desc())
        .execution_options(scope_bypass=True)
    )
    if session is None:
        session = TableSession(
            public_id=secrets.token_urlsafe(18),
            company_id=company.id,
            branch_id=table.branch_id,
            table_id=table.id,
            session_type=TableSessionType.DINE_IN,
            status=TableSessionStatus.OPEN,
            opened_by=None,
            opened_at=datetime.now(UTC),
        )
        db.add(session)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            session = db.scalar(
                select(TableSession)
                .where(
                    TableSession.table_id == table.id,
                    TableSession.company_id == company.id,
                    TableSession.branch_id == table.branch_id,
                    TableSession.status.in_(
                        [
                            TableSessionStatus.OPEN,
                            TableSessionStatus.BILL_REQUESTED,
                            TableSessionStatus.BILLED,
                        ]
                    ),
                )
                .order_by(TableSession.opened_at.desc(), TableSession.id.desc())
                .execution_options(scope_bypass=True)
            )
            if session is None:
                raise
    return resolve_qr_for_guest(db, raw_qr=raw_qr)
