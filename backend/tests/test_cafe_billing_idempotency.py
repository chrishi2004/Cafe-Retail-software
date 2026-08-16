from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Invoice, Sale, StockMovement
from tests.p7_fixtures import cafe_headers
from tests.p8_fixtures import create_mixed_served_table_orders, seed_p8


def test_same_billing_key_replays_original_invoice_and_changed_payload_conflicts(
    client, db_session_factory: sessionmaker[Session]
):
    ids = seed_p8(db_session_factory)
    create_mixed_served_table_orders(client, ids)
    headers = cafe_headers(client, "order_taker")
    quote = client.get(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/quote", headers=headers
    ).json()
    payload = {
        "expected_version": quote["source_version"],
        "payments": [{"payment_mode_id": ids["cash_mode"], "amount": quote["grand_total"]}],
    }
    first = client.post(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/bill",
        headers={**headers, "Idempotency-Key": "p8-idem-table-0001"},
        json=payload,
    )
    assert first.status_code == 200, first.text
    invoice_id = first.json()["receipt"]["invoice_id"]

    replay = client.post(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/bill",
        headers={**headers, "Idempotency-Key": "p8-idem-table-0001"},
        json=payload,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["receipt"]["invoice_id"] == invoice_id

    changed = client.post(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/bill",
        headers={**headers, "Idempotency-Key": "p8-idem-table-0001"},
        json={
            **payload,
            "payments": [{"payment_mode_id": ids["cash_mode"], "amount": "359.00"}],
        },
    )
    assert changed.status_code == 409

    second_key = client.post(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/bill",
        headers={**headers, "Idempotency-Key": "p8-different-key-0002"},
        json=payload,
    )
    assert second_key.status_code == 409

    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Invoice).where(Invoice.company_id == ids["cafe_company"])) == 1
        assert db.scalar(select(func.count()).select_from(Sale).where(Sale.company_id == ids["cafe_company"])) == 1
        movement_count = db.scalar(
            select(func.count()).select_from(StockMovement).where(StockMovement.company_id == ids["cafe_company"])
        )
        assert movement_count == 2
