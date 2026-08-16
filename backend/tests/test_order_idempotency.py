from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import CafeOrder, CafeOrderItem, CafeOrderStatusHistory
from tests.p6_fixtures import seed_p6_public_ordering


def _guest(client: TestClient, ids: dict[str, object]) -> tuple[str, dict[str, str]]:
    opened = client.post(f"/api/public/cafe/qr/{ids['raw_qr']}/resolve")
    assert opened.status_code == 200, opened.text
    return opened.json()["session_public_id"], {"X-Guest-Access": opened.json()["guest_access"]}


def test_identical_retry_returns_one_durable_order(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p6_public_ordering(db_session_factory)
    public_id, headers = _guest(client, ids)
    payload = {"items": [{"menu_item_public_id": ids["menu_item_public_id"], "quantity": 2}]}
    request_headers = {**headers, "Idempotency-Key": "p6-duplicate-tap-0001"}

    first = client.post(f"/api/public/cafe/sessions/{public_id}/orders", headers=request_headers, json=payload)
    second = client.post(f"/api/public/cafe/sessions/{public_id}/orders", headers=request_headers, json=payload)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["public_id"] == second.json()["public_id"]
    assert first.json()["order_number"] == second.json()["order_number"]
    assert second.json()["replayed"] is True

    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CafeOrder)) == 1
        assert db.scalar(select(func.count()).select_from(CafeOrderItem)) == 1
        assert db.scalar(select(func.count()).select_from(CafeOrderStatusHistory)) == 1


def test_same_retry_key_with_changed_payload_conflicts(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p6_public_ordering(db_session_factory)
    public_id, headers = _guest(client, ids)
    request_headers = {**headers, "Idempotency-Key": "p6-changed-retry-0001"}

    first = client.post(
        f"/api/public/cafe/sessions/{public_id}/orders",
        headers=request_headers,
        json={"items": [{"menu_item_public_id": ids["menu_item_public_id"], "quantity": 1}]},
    )
    changed = client.post(
        f"/api/public/cafe/sessions/{public_id}/orders",
        headers=request_headers,
        json={"items": [{"menu_item_public_id": ids["menu_item_public_id"], "quantity": 2}]},
    )

    assert first.status_code == 201
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "idempotency_conflict"
    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CafeOrder)) == 1
