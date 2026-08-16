from __future__ import annotations

from datetime import UTC, datetime

from tests.multi_venture_fixtures import login_headers, seed_two_ventures


def test_business_day_closing_tracks_counted_cash_variance_and_reopen(client, db_session_factory):
    ids = seed_two_ventures(db_session_factory)
    headers = {**login_headers(client, "owner@example.test"), "X-Venture-Id": "1"}
    business_date = datetime.now(UTC).date().isoformat()
    created = client.post(
        "/api/governance/closings",
        json={"branch_id": ids["retail_branch"], "business_date": business_date, "opening_cash": "100"},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    row = created.json()
    assert row["expected_cash"] == "100.00"

    submitted = client.post(
        f"/api/governance/closings/{row['id']}/submit",
        json={"counted_cash": "97.50"},
        headers=headers,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["variance"] == "-2.50"

    closed = client.post(f"/api/governance/closings/{row['id']}/close", headers=headers)
    assert closed.status_code == 200, closed.text
    reopened = client.post(
        f"/api/governance/closings/{row['id']}/reopen",
        json={"reason": "Correction required"},
        headers=headers,
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "reopened"
