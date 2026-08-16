from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.api.routes.public_cafe as public_routes
from tests.p6_fixtures import seed_p6_public_ordering


def _guest(client: TestClient, ids: dict[str, object]) -> tuple[str, str]:
    opened = client.post(f"/api/public/cafe/qr/{ids['raw_qr']}/resolve")
    assert opened.status_code == 200, opened.text
    return opened.json()["session_public_id"], opened.json()["guest_access"]


def test_qr_resolve_is_rate_limited_by_public_endpoint(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    monkeypatch,
) -> None:
    ids = seed_p6_public_ordering(db_session_factory)
    monkeypatch.setattr(public_routes, "PUBLIC_RESOLVE_LIMIT", 2)
    assert client.post(f"/api/public/cafe/qr/{ids['raw_qr']}/resolve").status_code == 200
    assert client.post(f"/api/public/cafe/qr/{ids['raw_qr']}/resolve").status_code == 200
    limited = client.post(f"/api/public/cafe/qr/{ids['raw_qr']}/resolve")
    assert limited.status_code == 429
    assert limited.headers.get("retry-after") is not None


def test_guest_writes_are_rate_limited_per_window(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    monkeypatch,
) -> None:
    ids = seed_p6_public_ordering(db_session_factory)
    public_id, access = _guest(client, ids)
    monkeypatch.setattr(public_routes, "PUBLIC_WRITE_LIMIT", 2)
    payload = {"items": [{"menu_item_public_id": ids["menu_item_public_id"], "quantity": 1}]}
    for suffix in ("01", "02"):
        response = client.post(
            f"/api/public/cafe/sessions/{public_id}/orders",
            headers={"X-Guest-Access": access, "Idempotency-Key": f"p6-rate-order-{suffix}"},
            json=payload,
        )
        assert response.status_code == 201, response.text
    limited = client.post(
        f"/api/public/cafe/sessions/{public_id}/orders",
        headers={"X-Guest-Access": access, "Idempotency-Key": "p6-rate-order-03"},
        json=payload,
    )
    assert limited.status_code == 429


def test_payload_quantity_item_count_and_declared_size_are_bounded(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    monkeypatch,
) -> None:
    ids = seed_p6_public_ordering(db_session_factory)
    public_id, access = _guest(client, ids)
    base_headers = {"X-Guest-Access": access}

    too_many = client.post(
        f"/api/public/cafe/sessions/{public_id}/orders",
        headers={**base_headers, "Idempotency-Key": "p6-limit-quantity"},
        json={"items": [{"menu_item_public_id": ids["menu_item_public_id"], "quantity": 21}]},
    )
    assert too_many.status_code == 422

    too_many_items = client.post(
        f"/api/public/cafe/sessions/{public_id}/orders",
        headers={**base_headers, "Idempotency-Key": "p6-limit-items-0001"},
        json={"items": [{"menu_item_public_id": f"public-item-{index:03d}", "quantity": 1} for index in range(26)]},
    )
    assert too_many_items.status_code == 422

    monkeypatch.setattr(public_routes, "PUBLIC_MAX_BODY_BYTES", 32)
    too_large = client.post(
        f"/api/public/cafe/sessions/{public_id}/orders",
        headers={**base_headers, "Idempotency-Key": "p6-limit-body-0001"},
        json={"items": [{"menu_item_public_id": ids["menu_item_public_id"], "quantity": 1}]},
    )
    assert too_large.status_code == 413
