from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from tests.multi_venture_fixtures import TEST_PASSWORD, login_headers
from tests.p4_fixtures import (
    add_cafe_operational_roles,
    configure_p4_ventures,
    prepare_retail_gst_activation,
)


def _activation_payload(effective_from: date) -> dict:
    return {
        "effective_from": effective_from.isoformat(),
        "acknowledge_professional_review": True,
        "confirmation": "ACTIVATE GST",
    }


def _quote(branch_id: int, product_id: int, invoice_type: str, invoice_date: date) -> dict:
    return {
        "branch_id": branch_id,
        "invoice_type": invoice_type,
        "invoice_date": datetime.combine(invoice_date, datetime.min.time(), tzinfo=UTC).isoformat(),
        "items": [{"product_id": product_id, "quantity": "1.00"}],
    }


def test_only_super_admin_can_activate_and_missing_prerequisites_fail(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = configure_p4_ventures(db_session_factory)
    add_cafe_operational_roles(db_session_factory, ids["cafe_branch"])
    tomorrow = date.today() + timedelta(days=1)

    for email in [
        "admin@hybridretail.test",
        "manager@hybridretail.test",
        "staff@hybridretail.test",
        "analyst@hybridretail.test",
        "cafe.admin@example.test",
        "ordertaker@example.com",
        "kitchen@example.com",
    ]:
        headers = login_headers(client, email)
        response = client.post("/api/tax-operation/activate-gst", headers=headers, json=_activation_payload(tomorrow))
        assert response.status_code == 403, (email, response.text)

    owner_headers = login_headers(client, "owner@example.test")
    retail_owner_headers = {**owner_headers, "X-Venture-Id": "1"}
    no_step_up = client.post(
        "/api/tax-operation/activate-gst",
        headers=retail_owner_headers,
        json=_activation_payload(tomorrow),
    )
    assert no_step_up.status_code == 403

    step_up = client.post(
        "/api/auth/step-up",
        headers=retail_owner_headers,
        json={"password": TEST_PASSWORD},
    )
    assert step_up.status_code == 200
    missing = client.post(
        "/api/tax-operation/activate-gst",
        headers=retail_owner_headers,
        json=_activation_payload(tomorrow),
    )
    assert missing.status_code == 400
    assert "prerequisites" in missing.json()["error"]["message"].lower()


def test_activation_is_effective_dated_and_historical_non_gst_is_unchanged(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = configure_p4_ventures(db_session_factory)
    prepare_retail_gst_activation(db_session_factory)
    admin_headers = login_headers(client, "admin@hybridretail.test")

    historical = client.post(
        "/api/invoices",
        headers=admin_headers,
        json=_quote(ids["retail_branch"], ids["retail_product"], "non_gst", date.today()),
    )
    assert historical.status_code == 201, historical.text
    historical_id = historical.json()["id"]
    before_tax_fields = {
        key: historical.json()[key]
        for key in ["invoice_type", "cgst_total", "sgst_total", "igst_total", "cess_total", "grand_total"]
    }

    owner_headers = login_headers(client, "owner@example.test")
    retail_owner_headers = {**owner_headers, "X-Venture-Id": "1"}
    assert client.post(
        "/api/auth/step-up",
        headers=retail_owner_headers,
        json={"password": TEST_PASSWORD},
    ).status_code == 200

    effective = date.today() + timedelta(days=1)
    activated = client.post(
        "/api/tax-operation/activate-gst",
        headers=retail_owner_headers,
        json=_activation_payload(effective),
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["default_tax_mode"] == "gst"
    assert activated.json()["gst_effective_from"] == effective.isoformat()

    before_effective_gst = client.post(
        "/api/pos/quote",
        headers=admin_headers,
        json=_quote(ids["retail_branch"], ids["retail_product"], "gst", date.today()),
    )
    assert before_effective_gst.status_code == 400

    before_effective_non_gst = client.post(
        "/api/pos/quote",
        headers=admin_headers,
        json=_quote(ids["retail_branch"], ids["retail_product"], "non_gst", date.today()),
    )
    assert before_effective_non_gst.status_code == 200

    after_effective = client.post(
        "/api/pos/quote",
        headers=admin_headers,
        json=_quote(ids["retail_branch"], ids["retail_product"], "gst", effective),
    )
    assert after_effective.status_code == 200, after_effective.text
    assert after_effective.json()["invoice_type"] == "gst"

    forced_non_gst_after_effective = client.post(
        "/api/pos/quote",
        headers=admin_headers,
        json=_quote(ids["retail_branch"], ids["retail_product"], "non_gst", effective),
    )
    assert forced_non_gst_after_effective.status_code == 400

    historical_after = client.get(f"/api/invoices/{historical_id}", headers=admin_headers)
    assert historical_after.status_code == 200
    after_tax_fields = {key: historical_after.json()[key] for key in before_tax_fields}
    assert after_tax_fields == before_tax_fields
    assert Decimal(historical_after.json()["cgst_total"]) == 0
