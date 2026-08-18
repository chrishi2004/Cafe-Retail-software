"""P1+ development seed entry point for the multi-venture schema.

The original seed generator remains the source for the rich Retail demo data.
This wrapper establishes the ownership hierarchy first, uses correctly scoped
users/branches, and then reuses the deterministic Retail data generators.
"""

from __future__ import annotations

import argparse
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from scripts import seed as legacy
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    AIChatMessage,
    AIChatSession,
    AuditLog,
    Branch,
    BusinessGroup,
    BusinessProfile,
    BusinessType,
    Category,
    Company,
    Customer,
    CustomerAddress,
    CustomerLedgerEntry,
    CustomerPayment,
    FiscalPeriod,
    Forecast,
    GSTRegistration,
    Inventory,
    InventoryBatch,
    Invoice,
    InvoiceItem,
    InvoicePayment,
    InvoiceSequence,
    InvoiceSequenceResetRule,
    InvoiceSequenceType,
    InvoiceStatusHistory,
    InvoiceTax,
    PaymentMode,
    PaymentModeType,
    PrintTemplate,
    PrintTemplateType,
    Product,
    ProductBarcode,
    ProductPriceHistory,
    ProductUnit,
    PurchaseOrder,
    PurchaseOrderItem,
    Sale,
    SaleItem,
    SerialNumber,
    StockMovement,
    Supplier,
    TaxMode,
    TaxRate,
    User,
    UserRole,
)

GROUP_ID = 1
RETAIL_COMPANY_ID = 1
CAFE_COMPANY_ID = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed deterministic Retail + ownership demo data.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing demo business data before reseeding. Local development only.",
    )
    return parser.parse_args()


def _operational_count(db: Session) -> int:
    models = (User, Branch, Product, Sale, Invoice)
    return sum(db.scalar(select(func.count()).select_from(model)) or 0 for model in models)


def reset_business_data(db: Session) -> None:
    # Child-first order is deliberate. P1 introduces company FKs across nearly
    # every root, so deleting Company before Branch/User would fail closed.
    for model in [
        AIChatMessage,
        AIChatSession,
        AuditLog,
        InvoicePayment,
        InvoiceTax,
        InvoiceStatusHistory,
        InvoiceItem,
        Invoice,
        CustomerPayment,
        CustomerLedgerEntry,
        CustomerAddress,
        Customer,
        Forecast,
        StockMovement,
        PurchaseOrderItem,
        PurchaseOrder,
        SaleItem,
        Sale,
        Inventory,
        SerialNumber,
        InventoryBatch,
        ProductPriceHistory,
        ProductBarcode,
        Product,
        ProductUnit,
        PrintTemplate,
        FiscalPeriod,
        InvoiceSequence,
        PaymentMode,
        TaxRate,
        GSTRegistration,
        BusinessProfile,
        User,
        Branch,
        Supplier,
        Category,
        Company,
        BusinessGroup,
    ]:
        db.execute(delete(model))
    db.commit()


def prepare_database(db: Session, *, reset: bool) -> None:
    if reset:
        reset_business_data(db)
        return
    if _operational_count(db):
        raise RuntimeError(
            "Database already contains operational data. Re-run with --reset only for local demo reseeding."
        )


def create_ownership(db: Session) -> tuple[BusinessGroup, Company, Company]:
    group = db.get(BusinessGroup, GROUP_ID)
    if group is None:
        group = BusinessGroup(
            id=GROUP_ID,
            name="Kalpvrik Business Group",
            legal_name="Kalpvrik Business Group",
            default_currency="INR",
            is_active=True,
        )
        db.add(group)
        db.flush()

    retail = db.get(Company, RETAIL_COMPANY_ID)
    if retail is None:
        retail = Company(
            id=RETAIL_COMPANY_ID,
            business_group_id=group.id,
            business_type=BusinessType.RETAIL,
            slug="retail",
            code=legacy.DEMO_COMPANY["code"],
            name=legacy.DEMO_COMPANY["name"],
            legal_name=legacy.DEMO_COMPANY["legal_name"],
            trade_name=legacy.DEMO_COMPANY["trade_name"],
            pan=legacy.DEMO_COMPANY["pan"],
            default_currency=legacy.DEMO_COMPANY["default_currency"],
            is_demo=True,
            is_active=True,
        )
        db.add(retail)
    else:
        retail.business_group_id = group.id
        retail.business_type = BusinessType.RETAIL
        retail.slug = "retail"
        retail.is_demo = True

    cafe = db.get(Company, CAFE_COMPANY_ID)
    if cafe is None:
        cafe = Company(
            id=CAFE_COMPANY_ID,
            business_group_id=group.id,
            business_type=BusinessType.CAFE,
            slug="cafe",
            code="KALPVRIK_CAFE",
            name="Kalpvrik Cafe Demo",
            legal_name="Kalpvrik Cafe Demo",
            trade_name="Kalpvrik Cafe",
            default_currency="INR",
            is_demo=True,
            is_active=True,
        )
        db.add(cafe)
    else:
        cafe.business_group_id = group.id
        cafe.business_type = BusinessType.CAFE
        cafe.slug = "cafe"
        cafe.is_demo = True

    db.flush()
    return group, retail, cafe


def create_branches(db: Session, retail: Company, cafe: Company) -> tuple[list[Branch], Branch]:
    retail_branches = [Branch(company_id=retail.id, **branch_data) for branch_data in legacy.BRANCHES]
    cafe_branch = Branch(
        company_id=cafe.id,
        name="Kalpvrik Cafe Bengaluru",
        address="Cafe Demo Outlet, Bengaluru",
        city="Bengaluru",
        manager_name="Cafe Partner",
        is_active=True,
    )
    db.add_all([*retail_branches, cafe_branch])
    db.flush()
    return retail_branches, cafe_branch


def create_retail_business_settings(db: Session, company: Company, branches: list[Branch]) -> None:
    primary_branch = next(branch for branch in branches if branch.name == "Central Market")
    primary_gst = legacy.BRANCH_GST_DETAILS[primary_branch.name]
    if db.scalar(select(BusinessProfile).where(BusinessProfile.company_id == company.id)) is None:
        db.add(
            BusinessProfile(
                company_id=company.id,
                legal_name=company.legal_name,
                trade_name=company.trade_name,
                pan=company.pan,
                email="admin@hybridretail.test",
                phone="080-4000-2026",
                address=primary_branch.address,
                city=primary_branch.city,
                state=primary_gst["state"],
                state_code=primary_gst["state_code"],
                pincode=primary_gst["pincode"],
                default_tax_mode=TaxMode.GST,
                default_currency="INR",
                terms_and_conditions="Demo Retail settings. Phase 4 introduces guarded Non-GST defaults.",
            )
        )

    for branch in branches:
        gst_details = legacy.BRANCH_GST_DETAILS[branch.name]
        db.add(
            GSTRegistration(
                company_id=company.id,
                branch_id=branch.id,
                gstin=gst_details["gstin"],
                legal_name=company.legal_name,
                trade_name=company.trade_name,
                state=gst_details["state"],
                state_code=gst_details["state_code"],
                address=branch.address,
                pincode=gst_details["pincode"],
                is_primary=branch.name == "Central Market",
                is_active=True,
            )
        )

    db.add_all(
        [
            TaxRate(name="GST Exempt 0%", rate_percent=legacy.money(0), cess_percent=legacy.money(0), description="Zero-rated or exempt demo items"),
            TaxRate(name="GST 5%", rate_percent=legacy.money(5), cess_percent=legacy.money(0), description="Common essential goods GST slab"),
            TaxRate(name="GST 12%", rate_percent=legacy.money(12), cess_percent=legacy.money(0), description="Standard demo GST slab"),
            TaxRate(name="GST 18%", rate_percent=legacy.money(18), cess_percent=legacy.money(0), description="General demo GST slab"),
            TaxRate(name="GST 28%", rate_percent=legacy.money(28), cess_percent=legacy.money(0), description="Higher demo GST slab"),
        ]
    )
    for order, (name, mode_type, requires_reference) in enumerate(
        [
            ("Cash", PaymentModeType.CASH, False),
            ("UPI", PaymentModeType.UPI, True),
            ("Card", PaymentModeType.CARD, True),
            ("Bank Transfer", PaymentModeType.BANK_TRANSFER, True),
            ("Credit", PaymentModeType.CREDIT, False),
        ],
        start=1,
    ):
        db.add(
            PaymentMode(
                company_id=company.id,
                name=name,
                mode_type=mode_type,
                requires_reference=requires_reference,
                display_order=order,
            )
        )

    db.add(
        InvoiceSequence(
            company_id=company.id,
            branch_id=None,
            invoice_type=InvoiceSequenceType.GST_INVOICE,
            fiscal_year="2026-2027",
            prefix="INV-2026-",
            next_number=1,
            padding=5,
            reset_rule=InvoiceSequenceResetRule.FISCAL_YEAR,
        )
    )
    db.add(
        FiscalPeriod(
            company_id=company.id,
            name="FY 2026-2027",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True,
            is_closed=False,
        )
    )
    db.add_all(
        [
            PrintTemplate(
                company_id=company.id,
                name="Default A4 GST Invoice",
                template_type=PrintTemplateType.A4_GST_INVOICE,
                is_default=True,
                settings_json={"paper": "A4", "show_hsn": True, "show_tax_breakup": True},
            ),
            PrintTemplate(
                company_id=company.id,
                name="Default 80mm POS Receipt",
                template_type=PrintTemplateType.POS_80MM,
                is_default=True,
                settings_json={"paper": "80mm", "show_tax_breakup": True},
            ),
        ]
    )
    db.flush()


def create_users(
    db: Session,
    group: BusinessGroup,
    retail: Company,
    cafe: Company,
    retail_branches: list[Branch],
    cafe_branch: Branch,
) -> dict[str, User]:
    password_hash = hash_password(legacy.DEMO_PASSWORD)
    users = {
        # Keep the deterministic Retail generator wired to a company-scoped
        # Venture Admin. The separate owner exercises the new global role without
        # weakening existing Retail service-level role guards before P2.
        "owner": User(
            business_group_id=group.id,
            company_id=None,
            branch_id=None,
            name="Puneet Dixit",
            email="owner@hybridretail.test",
            password_hash=password_hash,
            role=UserRole.SUPER_ADMIN,
        ),
        "admin": User(
            business_group_id=group.id,
            company_id=retail.id,
            branch_id=None,
            name="Aarav Sharma",
            email="admin@hybridretail.test",
            password_hash=password_hash,
            role=UserRole.ADMIN,
        ),
        "central_manager": User(
            business_group_id=group.id,
            company_id=retail.id,
            name="Ananya Rao",
            email="manager.central@hybridretail.test",
            password_hash=password_hash,
            role=UserRole.STORE_MANAGER,
            branch_id=retail_branches[0].id,
        ),
        "north_staff": User(
            business_group_id=group.id,
            company_id=retail.id,
            name="Kabir Verma",
            email="staff.north@hybridretail.test",
            password_hash=password_hash,
            role=UserRole.STAFF,
            branch_id=retail_branches[1].id,
        ),
        "lakeside_staff": User(
            business_group_id=group.id,
            company_id=retail.id,
            name="Diya Iyer",
            email="staff.lakeside@hybridretail.test",
            password_hash=password_hash,
            role=UserRole.STAFF,
            branch_id=retail_branches[2].id,
        ),
        "analyst": User(
            business_group_id=group.id,
            company_id=retail.id,
            name="Nisha Kapoor",
            email="analyst@hybridretail.test",
            password_hash=password_hash,
            role=UserRole.ANALYST,
        ),
        "cafe_admin": User(
            business_group_id=group.id,
            company_id=cafe.id,
            branch_id=None,
            name="Meera Cafe Admin",
            email="cafe.admin@example.com",
            password_hash=password_hash,
            role=UserRole.ADMIN,
        ),
        "cafe_manager": User(
            business_group_id=group.id,
            company_id=cafe.id,
            branch_id=cafe_branch.id,
            name="Arjun Cafe Manager",
            email="cafe.manager@example.com",
            password_hash=password_hash,
            role=UserRole.STORE_MANAGER,
        ),
        "cafe_order_taker": User(
            business_group_id=group.id,
            company_id=cafe.id,
            branch_id=cafe_branch.id,
            name="Rohan Order Taker",
            email="cafe.orders@example.com",
            password_hash=password_hash,
            role=UserRole.ORDER_TAKER,
        ),
        "cafe_kitchen": User(
            business_group_id=group.id,
            company_id=cafe.id,
            branch_id=cafe_branch.id,
            name="Isha Kitchen",
            email="cafe.kitchen@example.com",
            password_hash=password_hash,
            role=UserRole.KITCHEN,
        ),
        "cafe_analyst": User(
            business_group_id=group.id,
            company_id=cafe.id,
            branch_id=None,
            name="Nila Cafe Analyst",
            email="cafe.analyst@example.com",
            password_hash=password_hash,
            role=UserRole.ANALYST,
        ),
    }
    db.add_all(users.values())
    db.flush()
    return users


def seed_database(reset: bool) -> dict[str, int | str]:
    legacy.SEED_RANDOM.seed(legacy.SEED_VALUE)
    with SessionLocal() as db:
        prepare_database(db, reset=reset)
        group, retail, cafe = create_ownership(db)
        retail_branches, cafe_branch = create_branches(db, retail, cafe)
        create_retail_business_settings(db, retail, retail_branches)
        legacy.create_product_units(db)
        categories = legacy.create_categories(db)
        suppliers = legacy.create_suppliers(db)
        users = create_users(db, group, retail, cafe, retail_branches, cafe_branch)
        legacy.create_customers(db, retail_branches, users)
        products = legacy.create_products(db, categories, suppliers)
        legacy.create_inventory(db, retail_branches, products)
        legacy.create_sales(db, retail_branches, products, users)
        legacy.create_purchase_orders(db, retail_branches, products, users)
        legacy.create_demo_invoices(db, retail_branches, users)
        legacy.create_audit_logs(db, users)
        db.commit()

        return {
            "business_groups": db.scalar(select(func.count()).select_from(BusinessGroup)) or 0,
            "companies": db.scalar(select(func.count()).select_from(Company)) or 0,
            "retail_branches": len(retail_branches),
            "cafe_branches": 1 if cafe_branch.id else 0,
            "products": db.scalar(select(func.count()).select_from(Product)) or 0,
            "sales": db.scalar(select(func.count()).select_from(Sale)) or 0,
            "invoices": db.scalar(select(func.count()).select_from(Invoice)) or 0,
            "users": db.scalar(select(func.count()).select_from(User)) or 0,
            "history_start": legacy.START_DATE.isoformat(),
            "history_end": legacy.END_DATE.isoformat(),
        }


def main() -> None:
    args = parse_args()
    summary = seed_database(reset=args.reset)
    print("Multi-venture seed complete:")
    for key, value in summary.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
