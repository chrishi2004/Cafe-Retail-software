"""P4 development seed: P3 multi-venture data plus safe Non-GST operation defaults."""

from __future__ import annotations

import argparse

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    BusinessProfile,
    BusinessType,
    Company,
    CustomerDetailsOnBill,
    GSTRegistration,
    InvoiceSequence,
    InvoiceSequenceResetRule,
    InvoiceSequenceType,
    PrintTemplate,
    PrintTemplateType,
    TaxMode,
    TaxRegistrationStatus,
)
from scripts.seed_multi_venture import seed_database as seed_multi_venture


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed P4 Non-GST Retail and Cafe demo operation.")
    parser.add_argument("--reset", action="store_true")
    return parser.parse_args()


def apply_p4_defaults() -> None:
    with SessionLocal() as db:
        companies = list(db.scalars(select(Company).where(Company.is_active.is_(True))).all())
        for company in companies:
            profile = db.scalar(select(BusinessProfile).where(BusinessProfile.company_id == company.id))
            if profile is None:
                profile = BusinessProfile(
                    company_id=company.id,
                    legal_name=company.legal_name,
                    trade_name=company.trade_name,
                    pan=company.pan,
                    tax_registration_status=TaxRegistrationStatus.UNREGISTERED,
                    default_tax_mode=TaxMode.NON_GST,
                    customer_details_on_bill=CustomerDetailsOnBill.BASIC,
                    b2b_gst_enabled=False,
                    include_customer_in_gst_reports=False,
                    default_currency=company.default_currency,
                )
                db.add(profile)
            else:
                profile.tax_registration_status = TaxRegistrationStatus.UNREGISTERED
                profile.default_tax_mode = TaxMode.NON_GST
                profile.gst_effective_from = None
                profile.customer_details_on_bill = CustomerDetailsOnBill.BASIC
                profile.b2b_gst_enabled = False
                profile.include_customer_in_gst_reports = False

            for registration in db.scalars(
                select(GSTRegistration).where(GSTRegistration.company_id == company.id)
            ).all():
                registration.is_active = False
                registration.reference_only = True

            sequence = db.scalar(
                select(InvoiceSequence).where(
                    InvoiceSequence.company_id == company.id,
                    InvoiceSequence.branch_id.is_(None),
                    InvoiceSequence.invoice_type == InvoiceSequenceType.NON_GST_INVOICE,
                    InvoiceSequence.fiscal_year == "2026-2027",
                )
            )
            if sequence is None:
                db.add(
                    InvoiceSequence(
                        company_id=company.id,
                        branch_id=None,
                        invoice_type=InvoiceSequenceType.NON_GST_INVOICE,
                        fiscal_year="2026-2027",
                        prefix=("CAFE-BILL-2026-" if company.business_type == BusinessType.CAFE else "BILL-2026-"),
                        next_number=1,
                        padding=5,
                        reset_rule=InvoiceSequenceResetRule.FISCAL_YEAR,
                        is_active=True,
                    )
                )
            template = db.scalar(
                select(PrintTemplate).where(
                    PrintTemplate.company_id == company.id,
                    PrintTemplate.template_type == PrintTemplateType.NON_GST_INVOICE,
                )
            )
            if template is None:
                db.add(
                    PrintTemplate(
                        company_id=company.id,
                        name="Default Non-GST Invoice",
                        template_type=PrintTemplateType.NON_GST_INVOICE,
                        is_default=True,
                        is_active=True,
                        settings_json={"show_gstin": False, "show_applied_tax": False},
                    )
                )
        db.commit()


def main() -> None:
    args = parse_args()
    summary = seed_multi_venture(reset=args.reset)
    apply_p4_defaults()
    print("P4 Non-GST seed complete:")
    for key, value in summary.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
