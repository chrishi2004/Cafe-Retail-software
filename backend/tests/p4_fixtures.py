from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.models import (
    Branch,
    BusinessProfile,
    Company,
    CustomerDetailsOnBill,
    GSTRegistration,
    InvoiceSequence,
    InvoiceSequenceResetRule,
    InvoiceSequenceType,
    PrintTemplate,
    PrintTemplateType,
    Product,
    Sale,
    TaxMode,
    TaxRegistrationStatus,
    User,
    UserRole,
)
from tests.multi_venture_fixtures import TEST_PASSWORD, seed_two_ventures


def configure_p4_ventures(factory: sessionmaker[Session]) -> dict[str, int]:
    ids = seed_two_ventures(factory)
    with factory() as db:
        retail = db.get(Company, 1)
        cafe = db.get(Company, 2)
        assert retail is not None and cafe is not None
        retail_branch = db.get(Branch, ids["retail_branch"])
        cafe_branch = db.get(Branch, ids["cafe_branch"])
        assert retail_branch is not None and cafe_branch is not None

        db.add_all(
            [
                BusinessProfile(
                    company_id=1,
                    legal_name=retail.legal_name,
                    trade_name=retail.trade_name,
                    state="Karnataka",
                    state_code="29",
                    tax_registration_status=TaxRegistrationStatus.UNREGISTERED,
                    default_tax_mode=TaxMode.NON_GST,
                    customer_details_on_bill=CustomerDetailsOnBill.BASIC,
                    default_currency="INR",
                ),
                BusinessProfile(
                    company_id=2,
                    legal_name=cafe.legal_name,
                    trade_name=cafe.trade_name,
                    state="Karnataka",
                    state_code="29",
                    tax_registration_status=TaxRegistrationStatus.UNREGISTERED,
                    default_tax_mode=TaxMode.NON_GST,
                    customer_details_on_bill=CustomerDetailsOnBill.BASIC,
                    default_currency="INR",
                ),
            ]
        )
        db.add_all(
            [
                InvoiceSequence(
                    company_id=1,
                    branch_id=None,
                    invoice_type=InvoiceSequenceType.NON_GST_INVOICE,
                    fiscal_year="2026-2027",
                    prefix="BILL-",
                    next_number=1,
                    padding=5,
                    reset_rule=InvoiceSequenceResetRule.FISCAL_YEAR,
                    is_active=True,
                ),
                InvoiceSequence(
                    company_id=2,
                    branch_id=None,
                    invoice_type=InvoiceSequenceType.NON_GST_INVOICE,
                    fiscal_year="2026-2027",
                    prefix="CAFE-BILL-",
                    next_number=1,
                    padding=5,
                    reset_rule=InvoiceSequenceResetRule.FISCAL_YEAR,
                    is_active=True,
                ),
            ]
        )
        retail_product = db.get(Product, ids["retail_product"])
        cafe_product = db.get(Product, ids["cafe_product"])
        assert retail_product is not None and cafe_product is not None
        retail_product.hsn_sac_code = "21069099"
        cafe_product.hsn_sac_code = "21069099"
        db.commit()
    return ids


def prepare_retail_gst_activation(factory: sessionmaker[Session]) -> None:
    with factory() as db:
        profile = db.scalar(select(BusinessProfile).where(BusinessProfile.company_id == 1))
        company = db.get(Company, 1)
        assert profile is not None and company is not None
        profile.tax_registration_status = TaxRegistrationStatus.REGISTERED
        registration = GSTRegistration(
            company_id=1,
            branch_id=None,
            gstin="29ABCDE1234F1Z5",
            legal_name=company.legal_name,
            trade_name=company.trade_name,
            state="Karnataka",
            state_code="29",
            is_primary=True,
            is_active=True,
            reference_only=False,
        )
        db.add(registration)
        db.add(
            InvoiceSequence(
                company_id=1,
                branch_id=None,
                invoice_type=InvoiceSequenceType.GST_INVOICE,
                fiscal_year="2026-2027",
                prefix="GST-",
                next_number=1,
                padding=5,
                reset_rule=InvoiceSequenceResetRule.FISCAL_YEAR,
                is_active=True,
            )
        )
        db.add(
            PrintTemplate(
                company_id=1,
                name="GST Test Template",
                template_type=PrintTemplateType.A4_GST_INVOICE,
                is_default=True,
                is_active=True,
                settings_json={"test": True},
            )
        )
        db.commit()


def add_cafe_operational_roles(factory: sessionmaker[Session], cafe_branch_id: int) -> None:
    with factory() as db:
        for role, email in [
            (UserRole.ORDER_TAKER, "ordertaker@example.com"),
            (UserRole.KITCHEN, "kitchen@example.com"),
        ]:
            db.add(
                User(
                    business_group_id=1,
                    company_id=2,
                    branch_id=cafe_branch_id,
                    name=role.value,
                    email=email,
                    password_hash=hash_password(TEST_PASSWORD),
                    role=role,
                )
            )
        db.commit()


def add_turnover_rows(factory: sessionmaker[Session], ids: dict[str, int]) -> None:
    with factory() as db:
        retail_admin = db.scalar(select(User).where(User.email == "admin@hybridretail.test"))
        cafe_admin = db.get(User, ids["cafe_admin"])
        assert retail_admin is not None and cafe_admin is not None
        db.add_all(
            [
                Sale(
                    company_id=1,
                    sale_number="P4-RET-1",
                    branch_id=ids["retail_branch"],
                    sale_datetime=datetime.now(UTC),
                    subtotal=Decimal("100.00"),
                    discount_total=Decimal("0.00"),
                    tax_total=Decimal("0.00"),
                    total_amount=Decimal("100.00"),
                    created_by=retail_admin.id,
                ),
                Sale(
                    company_id=2,
                    sale_number="P4-CAFE-1",
                    branch_id=ids["cafe_branch"],
                    sale_datetime=datetime.now(UTC),
                    subtotal=Decimal("60.00"),
                    discount_total=Decimal("0.00"),
                    tax_total=Decimal("0.00"),
                    total_amount=Decimal("60.00"),
                    created_by=cafe_admin.id,
                ),
            ]
        )
        db.commit()
