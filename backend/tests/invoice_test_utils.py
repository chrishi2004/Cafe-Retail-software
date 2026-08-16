from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    Branch,
    BusinessProfile,
    GSTRegistration,
    Inventory,
    PrintTemplate,
    PrintTemplateType,
    TaxMode,
    TaxRegistrationStatus,
)


def login(client, email: str = "admin@hybridretail.test") -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "RetailDemo@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def central_branch_id(db_session_factory: sessionmaker[Session]) -> int:
    with db_session_factory() as db:
        branch = db.scalar(select(Branch).where(Branch.name == "Central Market"))
        assert branch is not None
        return branch.id


def configure_invoice_foundation(client, branch_id: int) -> dict[str, int]:
    headers = login(client)
    profile_response = client.put(
        "/api/business-profile",
        json={
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
            "terms_and_conditions": "Demo Non-GST profile with GST-ready reference metadata.",
        },
        headers=headers,
    )
    assert profile_response.status_code == 200, profile_response.text
    company_id = profile_response.json()["company_id"]

    tax_response = client.post(
        "/api/tax-rates",
        json={
            "name": "GST 18%",
            "rate_percent": "18.00",
            "cess_percent": "0.00",
            "description": "Internal GST-ready reference slab",
            "is_active": True,
        },
        headers=headers,
    )
    assert tax_response.status_code == 201
    tax_rate_id = tax_response.json()["id"]

    cash_response = client.post(
        "/api/payment-modes",
        json={
            "name": "Cash",
            "mode_type": "cash",
            "requires_reference": False,
            "display_order": 1,
            "is_active": True,
        },
        headers=headers,
    )
    assert cash_response.status_code == 201
    cash_mode_id = cash_response.json()["id"]

    for invoice_type, prefix in [("gst_invoice", "GST-2026-"), ("non_gst_invoice", "BILL-2026-")]:
        sequence_response = client.post(
            "/api/invoice-sequences",
            json={
                "company_id": company_id,
                "branch_id": None,
                "invoice_type": invoice_type,
                "fiscal_year": "2026-2027",
                "prefix": prefix,
                "suffix": None,
                "next_number": 1,
                "padding": 4,
                "reset_rule": "fiscal_year",
                "is_active": True,
            },
            headers=headers,
        )
        assert sequence_response.status_code == 201

    category_response = client.post(
        "/api/categories",
        json={"name": "POS Grocery", "description": "Billing products"},
        headers=headers,
    )
    assert category_response.status_code == 201
    supplier_response = client.post(
        "/api/suppliers",
        json={
            "name": "POS Supplier",
            "contact_person": "Asha Rao",
            "email": "pos.supplier@example.com",
            "phone": "9876500222",
            "address": "Wholesale Market",
            "payment_terms": "Net 15",
            "lead_time_days": 4,
            "is_active": True,
        },
        headers=headers,
    )
    assert supplier_response.status_code == 201

    product_response = client.post(
        "/api/products",
        json={
            "sku": "POS-SOAP-100",
            "name": "POS Bath Soap",
            "description": "GST-ready reference item billed Non-GST until activation",
            "category_id": category_response.json()["id"],
            "supplier_id": supplier_response.json()["id"],
            "gst_rate_id": tax_rate_id,
            "unit_cost": "60.00",
            "selling_price": "100.00",
            "hsn_sac_code": "3401",
            "cess_rate_percent": "0.00",
            "primary_barcode": "8902026999001",
            "unit_of_measure": "pcs",
            "mrp": "110.00",
            "brand": "PureCare",
            "manufacturer": "POS Supplier",
            "item_type": "goods",
            "batch_tracking_enabled": False,
            "serial_tracking_enabled": False,
            "expiry_tracking_enabled": False,
            "reorder_threshold": "5.00",
            "target_stock_level": "50.00",
            "is_active": True,
        },
        headers=headers,
    )
    assert product_response.status_code == 201
    product_id = product_response.json()["id"]

    customer_response = client.post(
        "/api/customers",
        json={
            "name": "Invoice Customer",
            "phone": "9876640001",
            "email": "invoice.customer@example.com",
            "gstin": "07ABCDE1234F1Z6",
            "billing_address": "21 Tax Street",
            "shipping_address": "21 Tax Street",
            "city": "Delhi",
            "state": "Delhi",
            "state_code": "07",
            "pincode": "110001",
            "branch_id": branch_id,
            "company_id": None,
            "credit_limit": "1000.00",
            "opening_balance": "0.00",
            "is_active": True,
        },
        headers=headers,
    )
    assert customer_response.status_code == 201

    return {
        "branch_id": branch_id,
        "company_id": company_id,
        "product_id": product_id,
        "customer_id": customer_response.json()["id"],
        "cash_mode_id": cash_mode_id,
        "tax_rate_id": tax_rate_id,
    }


def activate_gst_for_tests(
    db_session_factory: sessionmaker[Session],
    *,
    company_id: int,
    effective_from: date = date(2026, 5, 1),
) -> None:
    """Put an already configured test venture into an explicit activated GST state.

    This bypasses the HTTP activation ceremony only inside billing-engine tests.
    P4 activation authorization itself is tested separately in
    test_gst_activation_controls.py.
    """
    with db_session_factory() as db:
        profile = db.scalar(select(BusinessProfile).where(BusinessProfile.company_id == company_id))
        assert profile is not None
        profile.tax_registration_status = TaxRegistrationStatus.REGISTERED
        profile.default_tax_mode = TaxMode.GST
        profile.gst_effective_from = effective_from

        registration = db.scalar(
            select(GSTRegistration)
            .where(GSTRegistration.company_id == company_id, GSTRegistration.is_primary.is_(True))
            .order_by(GSTRegistration.id)
        )
        assert registration is not None
        registration.is_active = True
        registration.reference_only = False

        template = db.scalar(
            select(PrintTemplate).where(
                PrintTemplate.company_id == company_id,
                PrintTemplate.template_type == PrintTemplateType.A4_GST_INVOICE,
            )
        )
        if template is None:
            db.add(
                PrintTemplate(
                    company_id=company_id,
                    name="GST Billing Test Template",
                    template_type=PrintTemplateType.A4_GST_INVOICE,
                    is_default=True,
                    is_active=True,
                    settings_json={"test_only": True},
                )
            )
        db.commit()


def add_inventory(db_session_factory: sessionmaker[Session], product_id: int, branch_id: int, quantity: str = "20.00") -> None:
    with db_session_factory() as db:
        db.add(
            Inventory(
                product_id=product_id,
                branch_id=branch_id,
                quantity_on_hand=Decimal(quantity),
                quantity_reserved=Decimal("0.00"),
                quantity_on_order=Decimal("0.00"),
            )
        )
        db.commit()


def setup_invoice_data(client, db_session_factory: sessionmaker[Session], quantity: str = "20.00") -> dict[str, int]:
    branch_id = central_branch_id(db_session_factory)
    ids = configure_invoice_foundation(client, branch_id)
    add_inventory(db_session_factory, ids["product_id"], branch_id, quantity=quantity)
    return ids
