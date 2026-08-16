import json
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.models import GSTRegistration, Product, TaxRate
from tests.multi_venture_fixtures import login_headers
from tests.p4_fixtures import configure_p4_ventures


def test_non_gst_invoice_has_zero_applied_tax_and_no_gstin_output(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = configure_p4_ventures(db_session_factory)
    with db_session_factory() as db:
        reference_rate = TaxRate(
            name="P4 Reference GST 18%",
            rate_percent=Decimal("18.00"),
            cess_percent=Decimal("0.00"),
            description="Internal reference rate only",
            is_active=True,
        )
        db.add(reference_rate)
        db.flush()
        product = db.get(Product, ids["retail_product"])
        assert product is not None
        product.gst_rate_id = reference_rate.id
        db.add(
            GSTRegistration(
                company_id=1,
                branch_id=ids["retail_branch"],
                gstin="29ABCDE1234F1Z5",
                legal_name="Test Retail Private Limited",
                state="Karnataka",
                state_code="29",
                is_primary=True,
                is_active=False,
                reference_only=True,
            )
        )
        db.commit()

    headers = login_headers(client, "admin@hybridretail.test")
    response = client.post(
        "/api/invoices",
        headers=headers,
        json={
            "branch_id": ids["retail_branch"],
            "invoice_type": "non_gst",
            "items": [{"product_id": ids["retail_product"], "quantity": "1.00"}],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["invoice_type"] == "non_gst"
    assert Decimal(body["cgst_total"]) == 0
    assert Decimal(body["sgst_total"]) == 0
    assert Decimal(body["igst_total"]) == 0
    assert Decimal(body["cess_total"]) == 0
    assert body["taxes"] == []
    assert body["items"][0]["hsn_sac_code"] == "21069099"
    assert Decimal(body["items"][0]["gst_rate"]) == 0

    customer_facing_json = json.dumps(body).lower()
    assert "29abcde1234f1z5" not in customer_facing_json
    assert "gstin" not in customer_facing_json

    with db_session_factory() as db:
        product = db.get(Product, ids["retail_product"])
        assert product is not None
        assert product.hsn_sac_code == "21069099"
        assert product.gst_rate_id is not None
        stored_rate = db.get(TaxRate, product.gst_rate_id)
        assert stored_rate is not None
        assert stored_rate.rate_percent == Decimal("18.00")


def test_non_gst_reference_registration_stays_internal(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = configure_p4_ventures(db_session_factory)
    with db_session_factory() as db:
        db.add(
            GSTRegistration(
                company_id=2,
                branch_id=ids["cafe_branch"],
                gstin="29ABCDE1234F1Z5",
                legal_name="Test Cafe",
                state="Karnataka",
                state_code="29",
                is_primary=True,
                is_active=False,
                reference_only=True,
            )
        )
        db.commit()

    headers = login_headers(client, "cafe.admin@example.test")
    tax_state = client.get("/api/tax-operation", headers=headers)
    assert tax_state.status_code == 200
    body = tax_state.json()
    assert body["default_tax_mode"] == "non_gst"
    assert body["gst_registration_active"] is False
    assert body["gst_registration_configured"] is True
    assert body["gstin_masked"] != "29ABCDE1234F1Z5"
