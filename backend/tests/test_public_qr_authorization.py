from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import CafeGuestAccess, CafeOrder, TableQRToken, TableSession, TableSessionStatus
from tests.p6_fixtures import seed_p6_public_ordering


def _resolve(client: TestClient, ids: dict[str, object]) -> tuple[str, str]:
    response = client.post(f"/api/public/cafe/qr/{ids['raw_qr']}/resolve")
    assert response.status_code == 200, response.text
    return response.json()["session_public_id"], response.json()["guest_access"]


def test_guest_access_cannot_cross_table_session_or_use_internal_id(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p6_public_ordering(db_session_factory)
    public_id, access = _resolve(client, ids)
    headers = {"X-Guest-Access": access}

    assert client.get(f"/api/public/cafe/sessions/{public_id}x/menu", headers=headers).status_code == 404
    assert client.get(f"/api/public/cafe/sessions/{ids['table_session']}/menu", headers=headers).status_code == 404

    injected = client.post(
        f"/api/public/cafe/sessions/{public_id}/orders",
        headers={**headers, "Idempotency-Key": "p6-scope-injection-01"},
        json={
            "company_id": ids["cafe_company"],
            "branch_id": ids["cafe_branch"],
            "items": [{"menu_item_public_id": ids["menu_item_public_id"], "quantity": 1}],
        },
    )
    assert injected.status_code == 422
    with db_session_factory() as db:
        assert db.scalar(select(CafeOrder.id)) is None


def test_expired_guest_access_fails_with_generic_public_error(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p6_public_ordering(db_session_factory)
    public_id, access = _resolve(client, ids)
    reference = access.split(".", 1)[0]
    with db_session_factory() as db:
        row = db.scalar(
            select(CafeGuestAccess)
            .where(CafeGuestAccess.public_reference == reference)
            .execution_options(scope_bypass=True)
        )
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    response = client.get(
        f"/api/public/cafe/sessions/{public_id}/menu",
        headers={"X-Guest-Access": access},
    )
    assert response.status_code == 401
    assert "company" not in response.text.lower()
    assert "branch" not in response.text.lower()


def test_revoked_qr_and_closed_session_fail_closed(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p6_public_ordering(db_session_factory)
    public_id, access = _resolve(client, ids)

    with db_session_factory() as db:
        session = db.get(TableSession, ids["table_session"])
        assert session is not None
        session.status = TableSessionStatus.CLOSED
        session.closed_at = datetime.now(UTC)
        db.commit()

    denied_order = client.post(
        f"/api/public/cafe/sessions/{public_id}/orders",
        headers={"X-Guest-Access": access, "Idempotency-Key": "p6-closed-session-01"},
        json={"items": [{"menu_item_public_id": ids["menu_item_public_id"], "quantity": 1}]},
    )
    assert denied_order.status_code in {404, 409}

    with db_session_factory() as db:
        qr = db.scalar(
            select(TableQRToken)
            .where(TableQRToken.table_id == ids["table"])
            .execution_options(scope_bypass=True)
        )
        assert qr is not None
        qr.revoked_at = datetime.now(UTC)
        db.commit()

    revoked = client.post(f"/api/public/cafe/qr/{ids['raw_qr']}/resolve")
    assert revoked.status_code == 404
    assert "company" not in revoked.text.lower()
