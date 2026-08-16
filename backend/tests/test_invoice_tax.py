from sqlalchemy.orm import Session, sessionmaker

from tests.invoice_test_utils import activate_gst_for_tests, login, setup_invoice_data


def test_gst_invoice_uses_cgst_sgst_for_intrastate_supply(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = setup_invoice_data(client, db_session_factory)
    activate_gst_for_tests(db_session_factory, company_id=ids["company_id"])

    response = client.post(
        "/api/pos/checkout",
        json={
            "branch_id": ids["branch_id"],
            "customer_id": None,
            "invoice_type": "gst",
            "place_of_supply_state": "Karnataka",
            "place_of_supply_state_code": "29",
            "invoice_date": "2026-05-21T10:00:00+00:00",
            "items": [{"product_id": ids["product_id"], "quantity": "2.00", "discount": "0.00"}],
            "payments": [{"payment_mode_id": ids["cash_mode_id"], "amount": "236.00"}],
        },
        headers=login(client, email="staff@hybridretail.test"),
    )

    assert response.status_code == 201
    invoice = response.json()
    assert invoice["taxable_total"] == "200.00"
    assert invoice["cgst_total"] == "18.00"
    assert invoice["sgst_total"] == "18.00"
    assert invoice["igst_total"] == "0.00"
    assert invoice["grand_total"] == "236.00"
    assert {tax["tax_type"] for tax in invoice["taxes"]} == {"cgst", "sgst"}


def test_gst_invoice_uses_igst_for_interstate_supply(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = setup_invoice_data(client, db_session_factory)
    activate_gst_for_tests(db_session_factory, company_id=ids["company_id"])

    response = client.post(
        "/api/pos/checkout",
        json={
            "branch_id": ids["branch_id"],
            "customer_id": ids["customer_id"],
            "invoice_type": "gst",
            "place_of_supply_state": "Delhi",
            "place_of_supply_state_code": "07",
            "invoice_date": "2026-05-21T10:00:00+00:00",
            "items": [{"product_id": ids["product_id"], "quantity": "1.00", "discount": "0.00"}],
            "payments": [{"payment_mode_id": ids["cash_mode_id"], "amount": "118.00"}],
        },
        headers=login(client),
    )

    assert response.status_code == 201
    invoice = response.json()
    assert invoice["taxable_total"] == "100.00"
    assert invoice["cgst_total"] == "0.00"
    assert invoice["sgst_total"] == "0.00"
    assert invoice["igst_total"] == "18.00"
    assert invoice["grand_total"] == "118.00"
    assert {tax["tax_type"] for tax in invoice["taxes"]} == {"igst"}


def test_non_gst_invoice_stores_zero_tax_totals(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = setup_invoice_data(client, db_session_factory)

    response = client.post(
        "/api/pos/checkout",
        json={
            "branch_id": ids["branch_id"],
            "customer_id": None,
            "invoice_type": "non_gst",
            "place_of_supply_state": "Karnataka",
            "place_of_supply_state_code": "29",
            "invoice_date": "2026-05-21T10:00:00+00:00",
            "items": [{"product_id": ids["product_id"], "quantity": "1.00", "discount": "5.00"}],
            "payments": [{"payment_mode_id": ids["cash_mode_id"], "amount": "95.00"}],
        },
        headers=login(client),
    )

    assert response.status_code == 201
    invoice = response.json()
    assert invoice["subtotal"] == "100.00"
    assert invoice["discount_total"] == "5.00"
    assert invoice["taxable_total"] == "95.00"
    assert invoice["cgst_total"] == "0.00"
    assert invoice["sgst_total"] == "0.00"
    assert invoice["igst_total"] == "0.00"
    assert invoice["grand_total"] == "95.00"
    assert invoice["taxes"] == []
