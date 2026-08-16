from __future__ import annotations

from tests.p9_fixtures import login_headers, seed_p9


def test_cafe_export_is_cafe_only_and_consolidated_export_is_explicitly_ventured(client, db_session_factory):
    seed_p9(db_session_factory)
    cafe_export = client.get("/api/exports/cafe", headers=login_headers(client, "cafe.admin@example.test"))
    assert cafe_export.status_code == 200
    assert "venture,branch_id" in cafe_export.text
    assert "cafe" in cafe_export.text
    assert "Retail" not in cafe_export.text

    consolidated = client.get("/api/exports/consolidated", headers=login_headers(client, "owner@example.test"))
    assert consolidated.status_code == 200
    assert "venture,company_id" in consolidated.text
    assert "retail" in consolidated.text
    assert "cafe" in consolidated.text
