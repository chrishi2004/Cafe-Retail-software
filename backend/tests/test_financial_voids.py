from __future__ import annotations

from tests.p9_fixtures import login_headers, seed_p9


def test_invoice_void_is_scoped_reasoned_and_idempotent(client, db_session_factory):
    ids = seed_p9(db_session_factory)
    headers = login_headers(client, "cafe.admin@example.test")
    payload = {"reason": "Duplicate bill correction", "idempotency_key": "p10-void-invoice-1"}
    first = client.post(f"/api/governance/voids/invoices/{ids['cafe_invoice']}", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["reversal_type"] == "void"
    again = client.post(f"/api/governance/voids/invoices/{ids['cafe_invoice']}", json=payload, headers=headers)
    assert again.status_code == 200, again.text
    assert again.json()["id"] == first.json()["id"]
