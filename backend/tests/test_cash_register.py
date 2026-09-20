from __future__ import annotations

from tests.p7_fixtures import cafe_headers
from tests.p8_fixtures import advance_order_to_served, seed_p8


def test_register_session_reconciles_invoice_cash_and_drawer_movements(client, db_session_factory):
    ids = seed_p8(db_session_factory)
    order_headers = cafe_headers(client, "order_taker")
    opened = client.post(
        "/api/cash-register/sessions",
        headers=order_headers,
        json={"branch_id": ids["cafe_branch"], "opening_float": "100.00"},
    )
    assert opened.status_code == 200, opened.text
    session = opened.json()

    order = client.post(
        "/api/cafe/orders",
        headers=order_headers,
        json={
            "order_type": "takeaway",
            "branch_id": ids["cafe_branch"],
            "items": [{"menu_item_public_id": ids["menu_item_public_id"], "quantity": 1}],
        },
    )
    assert order.status_code == 201, order.text
    served = advance_order_to_served(client, order_headers, order.json()["public_id"])
    quote = client.get(f"/api/cafe/billing/orders/{served['public_id']}/quote", headers=order_headers)
    assert quote.status_code == 200, quote.text
    grand_total = quote.json()["grand_total"]
    billed = client.post(
        f"/api/cafe/billing/orders/{served['public_id']}/bill",
        headers={**order_headers, "Idempotency-Key": "register-bill-0001"},
        json={
            "expected_version": quote.json()["source_version"],
            "payments": [{"payment_mode_id": ids["cash_mode"], "amount": grand_total}],
        },
    )
    assert billed.status_code == 200, billed.text

    for key, movement_type, amount in (("register-out-0001", "cash_out", "20.00"), ("register-exp-0001", "expense", "5.00")):
        movement = client.post(
            f"/api/cash-register/sessions/{session['id']}/movements",
            headers=order_headers,
            json={"movement_type": movement_type, "amount": amount, "reason": "Test movement", "idempotency_key": key},
        )
        assert movement.status_code == 200, movement.text

    current = client.get(f"/api/cash-register/sessions/{session['id']}", headers=order_headers)
    assert current.status_code == 200, current.text
    summary = current.json()
    from decimal import Decimal
    assert summary["cash_collections"] == grand_total
    assert Decimal(summary["expected_cash"]) == Decimal("100.00") + Decimal(grand_total) - Decimal("25.00")
    assert {row["mode"] for row in summary["mode_totals"]} == {"cash"}

    expected = Decimal("100.00") + Decimal(grand_total) - Decimal("25.00")
    counted = client.post(
        f"/api/cash-register/sessions/{session['id']}/count",
        headers=cafe_headers(client, "manager"),
        json={"counted_cash": str(expected - Decimal("1.00"))},
    )
    assert counted.status_code == 200, counted.text
    assert counted.json()["variance"] == "-1.00"
    closed = client.post(f"/api/cash-register/sessions/{session['id']}/close", headers=cafe_headers(client, "manager"))
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"


def test_register_rejects_second_open_session_for_branch(client, db_session_factory):
    ids = seed_p8(db_session_factory)
    headers = cafe_headers(client, "order_taker")
    first = client.post(
        "/api/cash-register/sessions",
        headers=headers,
        json={"branch_id": ids["cafe_branch"], "opening_float": "0"},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/api/cash-register/sessions",
        headers=headers,
        json={"branch_id": ids["cafe_branch"], "opening_float": "0"},
    )
    assert second.status_code == 409, second.text
