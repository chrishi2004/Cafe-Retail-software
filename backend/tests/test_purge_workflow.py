from __future__ import annotations

from tests.p9_fixtures import login_headers, seed_p9


def test_purge_rejects_unknown_entity_without_creating_a_delete_path(client, db_session_factory):
    seed_p9(db_session_factory)
    headers = {**login_headers(client, "owner@example.test"), "X-Venture-Id": "2"}
    response = client.post(
        "/api/governance/purges",
        json={"entity_type": "arbitrary_table", "entity_id": 1, "reason": "cleanup", "backup_reference": "backup://disposable-1"},
        headers=headers,
    )
    assert response.status_code == 400, response.text


def test_cafe_admin_cannot_create_purge(client, db_session_factory):
    seed_p9(db_session_factory)
    response = client.post(
        "/api/governance/purges",
        json={"entity_type": "demo_cafe_order", "entity_id": 999, "reason": "cleanup", "backup_reference": "backup://disposable-1"},
        headers=login_headers(client, "cafe.admin@example.test"),
    )
    assert response.status_code == 403
