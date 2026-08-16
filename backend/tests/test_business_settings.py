from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import AuditLog, InvoiceSequence, InvoiceSequenceType, PaymentMode
from app.services.business_settings import generate_next_invoice_number


def login(client, email: str = "admin@hybridretail.test") -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "RetailDemo@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def business_profile_payload() -> dict:
    return {
        "company_code": "HYBRID_RETAIL",
        "legal_name": "Hybrid Retail Demo Private Limited",
        "trade_name": "Hybrid Retail Demo",
        "pan": "ABCDE1234F",
        "email": "admin@hybridretail.test",
        "phone": "080-4000-2026",
        "address": "14 MG Road",
        "city": "Bengaluru",
        "state": "Karnataka",
        "state_code": "29",
        "pincode": "560001",
        "gstin": "29ABCDE1234F1Z5",
        "default_tax_mode": "non_gst",
        "default_currency": "INR",
        "terms_and_conditions": "Demo Non-GST profile with internal GST reference metadata.",
    }


def configure_business_profile(client, headers: dict[str, str]) -> dict:
    response = client.put("/api/business-profile", json=business_profile_payload(), headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_admin_can_configure_business_profile(client) -> None:
    headers = login(client)
    profile = configure_business_profile(client, headers)
    read_response = client.get("/api/business-profile", headers=headers)

    assert read_response.status_code == 200
    assert profile["legal_name"] == "Hybrid Retail Demo Private Limited"
    assert profile["gstin"] == "29ABCDE1234F1Z5"
    assert profile["default_tax_mode"] == "non_gst"
    assert read_response.json()["company_code"] == "HYBRID_RETAIL"


def test_tax_rates_crud_and_validation(client) -> None:
    headers = login(client)
    configure_business_profile(client, headers)

    invalid_response = client.post(
        "/api/tax-rates",
        json={"name": "Invalid GST", "rate_percent": "-1.00", "cess_percent": "0.00", "description": None, "is_active": True},
        headers=headers,
    )
    create_response = client.post(
        "/api/tax-rates",
        json={"name": "GST 18%", "rate_percent": "18.00", "cess_percent": "0.00", "description": "General GST slab", "is_active": True},
        headers=headers,
    )
    tax_rate = create_response.json()
    update_response = client.put(
        f"/api/tax-rates/{tax_rate['id']}",
        json={**tax_rate, "description": "Updated slab"},
        headers=headers,
    )
    list_response = client.get("/api/tax-rates", headers=headers)

    assert invalid_response.status_code == 422
    assert create_response.status_code == 201
    assert update_response.status_code == 200
    assert update_response.json()["description"] == "Updated slab"
    assert [rate["name"] for rate in list_response.json()] == ["GST 18%"]


def test_payment_modes_are_stored_per_company(client, db_session_factory: sessionmaker[Session]) -> None:
    headers = login(client)
    profile = configure_business_profile(client, headers)
    response = client.post(
        "/api/payment-modes",
        json={"name": "UPI", "mode_type": "upi", "requires_reference": True, "display_order": 2, "is_active": True},
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["company_id"] == profile["company_id"]
    with db_session_factory() as db:
        payment_mode = db.scalar(select(PaymentMode).where(PaymentMode.name == "UPI"))
    assert payment_mode is not None
    assert payment_mode.mode_type.value == "upi"


def test_invoice_sequence_generation_increments_safely(client, db_session_factory: sessionmaker[Session]) -> None:
    headers = login(client)
    configure_business_profile(client, headers)
    response = client.post(
        "/api/invoice-sequences",
        json={
            "branch_id": None,
            "invoice_type": "non_gst_invoice",
            "fiscal_year": "2026-2027",
            "prefix": "BILL-2026-",
            "suffix": None,
            "next_number": 7,
            "padding": 4,
            "reset_rule": "fiscal_year",
            "is_active": True,
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["preview_next_number"] == "BILL-2026-0007"

    with db_session_factory() as db:
        first = generate_next_invoice_number(db, invoice_type=InvoiceSequenceType.NON_GST_INVOICE)
        second = generate_next_invoice_number(db, invoice_type=InvoiceSequenceType.NON_GST_INVOICE)
        sequence = db.scalar(select(InvoiceSequence))
        db.commit()

    assert first == "BILL-2026-0007"
    assert second == "BILL-2026-0008"
    assert sequence is not None
    assert sequence.next_number == 9


def test_non_admin_cannot_write_business_settings(client) -> None:
    admin_headers = login(client)
    configure_business_profile(client, admin_headers)
    manager_headers = login(client, email="manager@hybridretail.test")
    response = client.post(
        "/api/tax-rates",
        json={"name": "Blocked GST", "rate_percent": "5.00", "cess_percent": "0.00", "description": None, "is_active": True},
        headers=manager_headers,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_authenticated_users_can_read_business_settings(client) -> None:
    admin_headers = login(client)
    configure_business_profile(client, admin_headers)
    client.post(
        "/api/tax-rates",
        json={"name": "GST 5%", "rate_percent": "5.00", "cess_percent": "0.00", "description": None, "is_active": True},
        headers=admin_headers,
    )

    analyst_headers = login(client, email="analyst@hybridretail.test")
    profile_response = client.get("/api/business-profile", headers=analyst_headers)
    tax_response = client.get("/api/tax-rates", headers=analyst_headers)

    assert profile_response.status_code == 200
    assert profile_response.json()["default_currency"] == "INR"
    assert tax_response.status_code == 200
    assert tax_response.json()[0]["name"] == "GST 5%"


def test_business_settings_changes_are_audited(client, db_session_factory: sessionmaker[Session]) -> None:
    headers = login(client)
    configure_business_profile(client, headers)
    client.post(
        "/api/tax-rates",
        json={"name": "GST 12%", "rate_percent": "12.00", "cess_percent": "0.00", "description": None, "is_active": True},
        headers=headers,
    )

    with db_session_factory() as db:
        audit = db.scalar(select(AuditLog).where(AuditLog.action == "tax_rate.create"))

    assert audit is not None
    assert audit.entity_type == "tax_rate"
