from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from tests.multi_venture_fixtures import login_headers
from tests.p4_fixtures import add_turnover_rows, configure_p4_ventures


def _quote_payload(branch_id: int, product_id: int, invoice_type: str) -> dict:
    return {
        "branch_id": branch_id,
        "invoice_type": invoice_type,
        "items": [{"product_id": product_id, "quantity": "1.00"}],
    }


def test_retail_and_cafe_default_to_non_gst_and_forced_gst_fails(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = configure_p4_ventures(db_session_factory)
    retail_headers = login_headers(client, "admin@hybridretail.test")
    cafe_headers = login_headers(client, "cafe.admin@example.test")

    retail_state = client.get("/api/tax-operation", headers=retail_headers)
    cafe_state = client.get("/api/tax-operation", headers=cafe_headers)
    assert retail_state.status_code == 200
    assert cafe_state.status_code == 200
    assert retail_state.json()["default_tax_mode"] == "non_gst"
    assert cafe_state.json()["default_tax_mode"] == "non_gst"
    assert retail_state.json()["tax_registration_status"] == "unregistered"
    assert cafe_state.json()["tax_registration_status"] == "unregistered"

    for headers, branch_id, product_id in [
        (retail_headers, ids["retail_branch"], ids["retail_product"]),
        (cafe_headers, ids["cafe_branch"], ids["cafe_product"]),
    ]:
        forced = client.post(
            "/api/pos/quote",
            headers=headers,
            json=_quote_payload(branch_id, product_id, "gst"),
        )
        assert forced.status_code == 400
        assert "not active" in forced.json()["error"]["message"].lower()

        quote = client.post(
            "/api/pos/quote",
            headers=headers,
            json=_quote_payload(branch_id, product_id, "non_gst"),
        )
        assert quote.status_code == 200, quote.text
        body = quote.json()
        assert body["invoice_type"] == "non_gst"
        assert Decimal(body["cgst_total"]) == 0
        assert Decimal(body["sgst_total"]) == 0
        assert Decimal(body["igst_total"]) == 0
        assert Decimal(body["cess_total"]) == 0
        assert all(Decimal(item["gst_rate"]) == 0 for item in body["items"])


def test_combined_turnover_is_owner_only_and_sums_ventures(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = configure_p4_ventures(db_session_factory)
    add_turnover_rows(db_session_factory, ids)
    owner_headers = login_headers(client, "owner@example.test")
    cafe_headers = login_headers(client, "cafe.admin@example.test")

    denied = client.get("/api/tax-operation/combined-turnover", headers=cafe_headers)
    assert denied.status_code == 403

    result = client.get("/api/tax-operation/combined-turnover", headers=owner_headers)
    assert result.status_code == 200, result.text
    body = result.json()
    assert Decimal(body["combined_turnover"]) == Decimal("160.00")
    assert {row["business_type"] for row in body["ventures"]} == {"retail", "cafe"}
    assert "does not determine" in body["review_notice"].lower()
