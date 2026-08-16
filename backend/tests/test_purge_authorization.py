from __future__ import annotations

from tests.p9_fixtures import login_headers, seed_p9


def test_purge_approval_requires_step_up_and_requester_separation(client, db_session_factory):
    seed_p9(db_session_factory)
    headers = {**login_headers(client, "owner@example.test"), "X-Venture-Id": "2"}
    request = client.post(
        "/api/governance/purges",
        json={"entity_type": "arbitrary_table", "entity_id": 1, "reason": "cleanup", "backup_reference": "backup://disposable-1"},
        headers=headers,
    )
    assert request.status_code == 400


def test_step_up_rejects_invalid_password(client, db_session_factory):
    seed_p9(db_session_factory)
    response = client.post(
        "/api/governance/step-up",
        json={"password": "not-the-password"},
        headers=login_headers(client, "owner@example.test"),
    )
    assert response.status_code == 403
