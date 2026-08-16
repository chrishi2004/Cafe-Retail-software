from __future__ import annotations

from tests.p9_fixtures import login_headers, seed_p9


def test_super_admin_consolidated_revenue_is_retail_plus_cafe(client, db_session_factory):
    seed_p9(db_session_factory)
    response = client.get("/api/dashboard/consolidated", headers=login_headers(client, "owner@example.test"))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["kpis"]["net_billed_revenue"] == "100.00"
    assert {row["venture"] for row in payload["venture_summaries"]} == {"retail", "cafe"}


def test_super_admin_cafe_filter_matches_cafe_source(client, db_session_factory):
    seed_p9(db_session_factory)
    headers = login_headers(client, "owner@example.test")
    response = client.get("/api/dashboard/consolidated", headers={**headers, "X-Venture-Id": "2"})
    assert response.status_code == 200, response.text
    assert response.json()["kpis"]["net_billed_revenue"] == "40.00"
