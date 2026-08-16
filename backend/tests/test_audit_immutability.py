from __future__ import annotations

from tests.p9_fixtures import login_headers, seed_p9


def test_audit_and_tombstone_delete_endpoints_do_not_exist(client, db_session_factory):
    seed_p9(db_session_factory)
    headers = login_headers(client, "owner@example.test")
    assert client.delete("/api/governance/audit/1", headers=headers).status_code == 404
    assert client.delete("/api/governance/tombstones/1", headers=headers).status_code == 404
