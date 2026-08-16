"""Verify PostgreSQL allows exactly one concurrent active session per Cafe table."""

from __future__ import annotations

import secrets
import threading

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models import BusinessType, CafeTable, Company, TableSession, TableSessionStatus, TableSessionType


def main() -> None:
    with SessionLocal() as db:
        cafe = db.scalar(select(Company).where(Company.business_type == BusinessType.CAFE))
        if cafe is None:
            raise RuntimeError("P5 Cafe seed is required before concurrency verification.")
        table = db.scalar(
            select(CafeTable).where(CafeTable.company_id == cafe.id, CafeTable.is_active.is_(True)).order_by(CafeTable.id)
        )
        if table is None:
            raise RuntimeError("P5 Cafe table seed is required before concurrency verification.")
        table_id = table.id
        company_id = table.company_id
        branch_id = table.branch_id
        db.execute(delete(TableSession).where(TableSession.table_id == table_id))
        db.commit()

    barrier = threading.Barrier(2)
    results: list[str] = []
    result_lock = threading.Lock()

    def attempt() -> None:
        with SessionLocal() as db:
            session = TableSession(
                company_id=company_id,
                branch_id=branch_id,
                table_id=table_id,
                public_id=secrets.token_urlsafe(18),
                session_type=TableSessionType.DINE_IN,
                status=TableSessionStatus.OPEN,
                opened_by=None,
            )
            db.add(session)
            barrier.wait()
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                outcome = "conflict"
            else:
                outcome = "success"
            with result_lock:
                results.append(outcome)

    threads = [threading.Thread(target=attempt), threading.Thread(target=attempt)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
        if thread.is_alive():
            raise RuntimeError("Concurrent session verification thread did not finish.")

    with SessionLocal() as db:
        active_count = db.scalar(
            select(func.count()).select_from(TableSession).where(
                TableSession.table_id == table_id,
                TableSession.status.in_(
                    [
                        TableSessionStatus.OPEN,
                        TableSessionStatus.BILL_REQUESTED,
                        TableSessionStatus.BILLED,
                    ]
                ),
            )
        )

    if sorted(results) != ["conflict", "success"]:
        raise RuntimeError(f"Expected one success and one conflict, got {results!r}.")
    if active_count != 1:
        raise RuntimeError(f"Expected exactly one active table session, found {active_count}.")

    print("P5 concurrency verification passed: one active session committed, one conflicted.")


if __name__ == "__main__":
    main()
