from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.p9_fixtures import login_headers, seed_p9


def test_cafe_dashboard_reconciles_orders_bills_collections_and_open_sessions(client, db_session_factory):
    seed_p9(db_session_factory)
    response = client.get(
        "/api/dashboard/cafe",
        params={
            "start_date": (datetime.now(UTC).date() - timedelta(days=1)).isoformat(),
            "end_date": datetime.now(UTC).date().isoformat(),
        },
        headers=login_headers(client, "cafe.admin@example.test"),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["venture"] == "cafe"
    assert payload["kpis"]["order_count"] == 1
    assert payload["kpis"]["ordered_value"] == "60.00"
    assert payload["kpis"]["billed_revenue"] == "40.00"
    assert payload["kpis"]["collections"] == "40.00"
    assert payload["kpis"]["cancelled_value"] == "20.00"
    assert payload["kpis"]["open_unbilled_sessions"] == 1
    assert "Retail Secret Product" not in response.text
