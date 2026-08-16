from __future__ import annotations

import argparse
import random
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    AIChatMessage,
    AIChatSession,
    AuditLog,
    Branch,
    BusinessProfile,
    Category,
    Company,
    Customer,
    CustomerAddress,
    CustomerAddressType,
    CustomerLedgerEntry,
    CustomerLedgerEntryType,
    CustomerPayment,
    FiscalPeriod,
    Forecast,
    GSTRegistration,
    InventoryBatch,
    Inventory,
    Invoice,
    InvoiceItem,
    InvoicePayment,
    InvoiceStatusHistory,
    InvoiceTax,
    InvoiceSequence,
    InvoiceSequenceResetRule,
    InvoiceSequenceType,
    PaymentMode,
    PaymentModeType,
    Product,
    ProductBarcode,
    ProductItemType,
    ProductPriceHistory,
    ProductUnit,
    PrintTemplate,
    PrintTemplateType,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    Sale,
    SaleItem,
    SerialNumber,
    StockMovement,
    StockMovementType,
    Supplier,
    TaxMode,
    TaxRate,
    User,
    UserRole,
)

SEED_VALUE = 20260518
SEED_RANDOM = random.Random(SEED_VALUE)
END_DATE = date(2026, 5, 18)
START_DATE = END_DATE - timedelta(days=270)
DEMO_PASSWORD = "RetailDemo@123"
RECENT_SLOW_MOVING_CUTOFF = END_DATE - timedelta(days=90)
RECENTLY_INACTIVE_SKUS = {
    "GRC-PNB-340",
    "PCR-DEO-150",
    "HHD-AFR-250",
    "STN-MKR-004",
    "STN-STP-SML",
}

DEMO_COMPANY = {
    "code": "HYBRID_RETAIL",
    "name": "Hybrid Retail Demo",
    "legal_name": "Hybrid Retail Demo Private Limited",
    "trade_name": "Hybrid Retail Demo",
    "pan": "ABCDE1234F",
    "default_currency": "INR",
}

BRANCH_GST_DETAILS = {
    "Central Market": {
        "gstin": "29ABCDE1234F1Z5",
        "state": "Karnataka",
        "state_code": "29",
        "pincode": "560001",
    },
    "Northside Express": {
        "gstin": "07ABCDE1234F1Z6",
        "state": "Delhi",
        "state_code": "07",
        "pincode": "110001",
    },
    "Lakeside Daily": {
        "gstin": "27ABCDE1234F1Z7",
        "state": "Maharashtra",
        "state_code": "27",
        "pincode": "411001",
    },
}

BRANCHES = [
    {
        "name": "Central Market",
        "address": "14 MG Road",
        "city": "Bengaluru",
        "manager_name": "Ananya Rao",
    },
    {
        "name": "Northside Express",
        "address": "88 Ring Road",
        "city": "Delhi",
        "manager_name": "Rohan Mehta",
    },
    {
        "name": "Lakeside Daily",
        "address": "21 Lake View Street",
        "city": "Pune",
        "manager_name": "Meera Nair",
    },
]

CUSTOMERS = [
    ("Ravi Kumar", "9876610001", "ravi.kumar@example.com", None, "Central Market", "Karnataka", "29", 12000, 1800, "B2C monthly grocery credit"),
    ("Asha Stores", "9876610002", "accounts@ashastores.example.com", "29AAECA1234F1Z2", "Central Market", "Karnataka", "29", 45000, 12500, "GST customer for office supplies"),
    ("Meera Nair", "9876610003", "meera.nair@example.com", None, "Lakeside Daily", "Maharashtra", "27", 8000, 0, "Regular prepaid customer"),
    ("Northside Cafe", "9876610004", "billing@northsidecafe.example.com", "07AAGCN5522K1Z8", "Northside Express", "Delhi", "07", 65000, 22000, "B2B cafe supplies"),
    ("Prakash Stationers", "9876610005", "prakash.stationers@example.com", "27AAICP7788M1Z4", "Lakeside Daily", "Maharashtra", "27", 35000, 7600, "Stationery reseller"),
    ("Diya Iyer", "9876610006", "diya.iyer@example.com", None, "Lakeside Daily", "Maharashtra", "27", 6000, 950, "Local household customer"),
    ("Urban Workspace LLP", "9876610007", "finance@urbanworkspace.example.com", "29AAFFU9988L1Z9", "Central Market", "Karnataka", "29", 90000, 31000, "Office pantry customer"),
    ("Green Basket Hostel", "9876610008", "admin@greenbasket.example.com", None, "Northside Express", "Delhi", "07", 25000, 4200, "Weekly hostel supplies"),
    ("Sonia Dutta", "9876610009", "sonia.dutta@example.com", None, "Central Market", "Karnataka", "29", 5000, 0, "Cash customer profile"),
    ("BlueLine Services", "9876610010", "accounts@blueline.example.com", "07AABCB1122L1Z5", "Northside Express", "Delhi", "07", 55000, 14200, "Corporate GST customer"),
    ("Kabir Malhotra", "9876610011", "kabir.m@example.com", None, "Northside Express", "Delhi", "07", 7000, 1200, "Personal credit account"),
    ("Fresh Office Pune", "9876610012", "pune@freshoffice.example.com", "27AADCF2211R1Z3", "Lakeside Daily", "Maharashtra", "27", 48000, 18000, "Office pantry and stationery"),
]

CATEGORIES = [
    ("Grocery", "Staple grocery and packaged food items"),
    ("Beverages", "Tea, coffee, juices, and bottled drinks"),
    ("Dairy", "Milk, curd, paneer, cheese, and butter"),
    ("Snacks", "Packaged snacks and quick bites"),
    ("Personal Care", "Everyday hygiene and grooming products"),
    ("Household", "Cleaning, laundry, and household supplies"),
    ("Stationery", "Office and school stationery products"),
]

SUPPLIERS = [
    ("FreshLine Distributors", "Kavita Shah", "freshline@example.com", "9876500101", 2, "Net 15"),
    ("Urban Pantry Wholesale", "Irfan Khan", "urbanpantry@example.com", "9876500102", 4, "Net 30"),
    ("DairyPure Logistics", "Neha Kulkarni", "dairypure@example.com", "9876500103", 1, "Due on receipt"),
    ("Beverage Hub India", "Arjun Bose", "beveragehub@example.com", "9876500104", 5, "Net 21"),
    ("QuickBite Foods", "Priya Menon", "quickbite@example.com", "9876500105", 3, "Net 15"),
    ("CleanHome Supplies", "Rakesh Sinha", "cleanhome@example.com", "9876500106", 7, "Net 30"),
    ("Daily Essentials Co", "Dev Patel", "dailyessentials@example.com", "9876500107", 4, "Net 20"),
    ("PaperTrail Stationers", "Fatima Ali", "papertrail@example.com", "9876500108", 6, "Net 30"),
    ("HealthCare Basics", "Sonia Dutta", "healthcare@example.com", "9876500109", 5, "Net 15"),
    ("Morning Basket Foods", "Vikram Jain", "morningbasket@example.com", "9876500110", 2, "Net 15"),
    ("Prime Household Mart", "Tara Joshi", "primehousehold@example.com", "9876500111", 8, "Net 45"),
    ("SchoolDesk Traders", "Kabir Malhotra", "schooldesk@example.com", "9876500112", 5, "Net 30"),
]

PRODUCT_CATALOG = {
    "Grocery": [
        ("Rice Premium 5kg", "GRC-RIC-5KG", "Urban Pantry Wholesale", 360, 485, 40, 180, "fast"),
        ("Wheat Flour 5kg", "GRC-WHF-5KG", "Morning Basket Foods", 240, 340, 38, 160, "fast"),
        ("Toor Dal 1kg", "GRC-TDL-1KG", "FreshLine Distributors", 105, 158, 35, 150, "fast"),
        ("Sugar 1kg", "GRC-SGR-1KG", "Daily Essentials Co", 42, 58, 45, 190, "fast"),
        ("Salt 1kg", "GRC-SLT-1KG", "Daily Essentials Co", 18, 28, 30, 120, "steady"),
        ("Cooking Oil 1L", "GRC-OIL-1LT", "Urban Pantry Wholesale", 120, 168, 36, 140, "fast"),
        ("Masala Mix 100g", "GRC-MAS-100", "Morning Basket Foods", 34, 55, 25, 100, "steady"),
        ("Pasta 500g", "GRC-PAS-500", "Urban Pantry Wholesale", 70, 110, 18, 80, "slow"),
        ("Tomato Ketchup 500g", "GRC-KET-500", "FreshLine Distributors", 62, 99, 22, 90, "steady"),
        ("Peanut Butter 340g", "GRC-PNB-340", "Morning Basket Foods", 135, 215, 12, 55, "slow"),
    ],
    "Beverages": [
        ("Tea Powder 500g", "BEV-TEA-500", "Beverage Hub India", 155, 235, 30, 130, "fast"),
        ("Instant Coffee 100g", "BEV-COF-100", "Beverage Hub India", 180, 285, 16, 70, "steady"),
        ("Orange Juice 1L", "BEV-ORG-1LT", "FreshLine Distributors", 78, 125, 24, 110, "fast"),
        ("Apple Juice 1L", "BEV-APL-1LT", "FreshLine Distributors", 82, 132, 20, 95, "steady"),
        ("Mineral Water 1L", "BEV-WTR-1LT", "Daily Essentials Co", 12, 20, 75, 280, "fast"),
        ("Energy Drink 250ml", "BEV-ENG-250", "Beverage Hub India", 55, 95, 22, 95, "steady"),
        ("Soda 750ml", "BEV-SOD-750", "Beverage Hub India", 28, 45, 32, 130, "steady"),
        ("Coconut Water 200ml", "BEV-COW-200", "FreshLine Distributors", 24, 42, 28, 120, "fast"),
        ("Cold Coffee 200ml", "BEV-CCF-200", "DairyPure Logistics", 26, 48, 26, 110, "steady"),
        ("Green Tea 25 Bags", "BEV-GRT-025", "Beverage Hub India", 95, 160, 10, 45, "slow"),
    ],
    "Dairy": [
        ("Milk 1L", "DRY-MLK-1LT", "DairyPure Logistics", 42, 58, 80, 320, "fast"),
        ("Curd 500g", "DRY-CRD-500", "DairyPure Logistics", 32, 52, 40, 170, "fast"),
        ("Paneer 200g", "DRY-PNR-200", "DairyPure Logistics", 70, 115, 24, 100, "fast"),
        ("Butter 100g", "DRY-BTR-100", "DairyPure Logistics", 45, 66, 26, 110, "steady"),
        ("Cheese Slices 200g", "DRY-CHS-200", "DairyPure Logistics", 95, 155, 18, 80, "steady"),
        ("Flavoured Yogurt 100g", "DRY-YOG-100", "DairyPure Logistics", 18, 32, 34, 140, "steady"),
        ("Lassi 200ml", "DRY-LAS-200", "DairyPure Logistics", 14, 25, 45, 180, "fast"),
        ("Ghee 500ml", "DRY-GHE-500", "Morning Basket Foods", 245, 355, 12, 50, "slow"),
        ("Cream 200ml", "DRY-CRM-200", "DairyPure Logistics", 55, 85, 14, 60, "slow"),
        ("Ice Cream Cup 100ml", "DRY-ICE-100", "DairyPure Logistics", 18, 35, 40, 160, "seasonal"),
    ],
    "Snacks": [
        ("Potato Chips 52g", "SNK-CHP-052", "QuickBite Foods", 18, 30, 60, 240, "fast"),
        ("Nachos 90g", "SNK-NCH-090", "QuickBite Foods", 38, 65, 30, 125, "steady"),
        ("Cookies 150g", "SNK-CKS-150", "QuickBite Foods", 42, 72, 34, 150, "fast"),
        ("Chocolate Bar 40g", "SNK-CHO-040", "QuickBite Foods", 22, 40, 55, 210, "fast"),
        ("Namkeen 200g", "SNK-NAM-200", "QuickBite Foods", 36, 62, 34, 145, "steady"),
        ("Cup Noodles 70g", "SNK-NDL-070", "QuickBite Foods", 28, 48, 32, 135, "steady"),
        ("Popcorn 100g", "SNK-POP-100", "QuickBite Foods", 30, 55, 20, 85, "slow"),
        ("Protein Bar 50g", "SNK-PRB-050", "HealthCare Basics", 58, 105, 15, 65, "slow"),
        ("Trail Mix 200g", "SNK-TRM-200", "HealthCare Basics", 115, 190, 10, 45, "slow"),
        ("Biscuits Family Pack", "SNK-BIS-FAM", "QuickBite Foods", 48, 80, 42, 170, "fast"),
    ],
    "Personal Care": [
        ("Shampoo 180ml", "PCR-SHM-180", "HealthCare Basics", 82, 145, 16, 75, "steady"),
        ("Toothpaste 150g", "PCR-TOP-150", "HealthCare Basics", 56, 95, 26, 110, "fast"),
        ("Bath Soap 100g", "PCR-SOP-100", "HealthCare Basics", 24, 42, 40, 160, "fast"),
        ("Handwash 250ml", "PCR-HDW-250", "HealthCare Basics", 55, 95, 22, 95, "steady"),
        ("Face Wash 100ml", "PCR-FCW-100", "HealthCare Basics", 105, 185, 12, 50, "slow"),
        ("Body Lotion 200ml", "PCR-BDL-200", "HealthCare Basics", 120, 210, 10, 45, "slow"),
        ("Sanitary Pads 8pc", "PCR-SPD-008", "HealthCare Basics", 48, 82, 24, 100, "steady"),
        ("Deodorant 150ml", "PCR-DEO-150", "HealthCare Basics", 115, 210, 12, 50, "slow"),
        ("Hair Oil 200ml", "PCR-HOL-200", "HealthCare Basics", 75, 128, 18, 80, "steady"),
        ("Tissue Box 100 Pulls", "PCR-TIS-100", "Daily Essentials Co", 38, 65, 28, 120, "steady"),
    ],
    "Household": [
        ("Dishwash Liquid 500ml", "HHD-DWL-500", "CleanHome Supplies", 58, 98, 22, 90, "steady"),
        ("Detergent Powder 1kg", "HHD-DTG-1KG", "CleanHome Supplies", 82, 132, 28, 120, "fast"),
        ("Floor Cleaner 1L", "HHD-FCL-1LT", "Prime Household Mart", 88, 150, 16, 75, "steady"),
        ("Toilet Cleaner 500ml", "HHD-TCL-500", "Prime Household Mart", 65, 112, 18, 80, "steady"),
        ("Garbage Bags 30pc", "HHD-GBG-030", "Prime Household Mart", 72, 125, 20, 85, "steady"),
        ("Kitchen Towels 2 Roll", "HHD-KTW-002", "Prime Household Mart", 95, 155, 14, 60, "slow"),
        ("Air Freshener 250ml", "HHD-AFR-250", "CleanHome Supplies", 110, 195, 10, 45, "slow"),
        ("Mosquito Repellent", "HHD-MSR-001", "Prime Household Mart", 78, 130, 24, 100, "seasonal"),
        ("Scrub Pads 5pc", "HHD-SCP-005", "CleanHome Supplies", 32, 58, 24, 105, "steady"),
        ("Laundry Bar 250g", "HHD-LBR-250", "CleanHome Supplies", 20, 35, 42, 170, "fast"),
    ],
    "Stationery": [
        ("Notebook 200 Pages", "STN-NBK-200", "PaperTrail Stationers", 38, 65, 24, 110, "steady"),
        ("Ball Pen Blue 10pc", "STN-PEN-010", "SchoolDesk Traders", 42, 75, 20, 90, "steady"),
        ("Pencil Pack 10pc", "STN-PCL-010", "SchoolDesk Traders", 25, 45, 18, 80, "steady"),
        ("A4 Paper 500 Sheets", "STN-A4P-500", "PaperTrail Stationers", 210, 320, 10, 45, "slow"),
        ("Sticky Notes 100 Sheets", "STN-STN-100", "PaperTrail Stationers", 35, 65, 12, 55, "slow"),
        ("Marker Set 4pc", "STN-MKR-004", "SchoolDesk Traders", 72, 125, 8, 38, "slow"),
        ("Glue Stick 15g", "STN-GLU-015", "SchoolDesk Traders", 18, 32, 14, 65, "steady"),
        ("Stapler Small", "STN-STP-SML", "PaperTrail Stationers", 65, 115, 8, 35, "slow"),
        ("File Folder 10pc", "STN-FLD-010", "SchoolDesk Traders", 55, 95, 12, 55, "slow"),
        ("Eraser 5pc", "STN-ERS-005", "SchoolDesk Traders", 12, 25, 18, 80, "steady"),
    ],
}

PRODUCT_UNIT_DEFINITIONS = [
    ("Piece", "pcs", "Default retail unit"),
    ("Kilogram", "kg", "Weight-based packaged goods"),
    ("Gram", "g", "Small packaged goods"),
    ("Litre", "l", "Liquid goods sold by litre"),
    ("Millilitre", "ml", "Small liquid packs"),
    ("Pack", "pack", "Multi-piece packaged items"),
    ("Box", "box", "Boxed retail items"),
]

CATEGORY_TAX_RATE_NAMES = {
    "Grocery": "GST 5%",
    "Beverages": "GST 12%",
    "Dairy": "GST 5%",
    "Snacks": "GST 12%",
    "Personal Care": "GST 18%",
    "Household": "GST 18%",
    "Stationery": "GST 12%",
}

CATEGORY_HSN_CODES = {
    "Grocery": "1006",
    "Beverages": "2202",
    "Dairy": "0401",
    "Snacks": "1905",
    "Personal Care": "3305",
    "Household": "3402",
    "Stationery": "4820",
}

CATEGORY_BRANDS = {
    "Grocery": ["DailyHarvest", "UrbanPantry", "MorningBasket"],
    "Beverages": ["BeverageHub", "FreshSip", "CoolLeaf"],
    "Dairy": ["DairyPure", "FarmFresh", "CreamLine"],
    "Snacks": ["QuickBite", "SnackKart", "MunchBox"],
    "Personal Care": ["HealthCare Basics", "PureCare", "UrbanGlow"],
    "Household": ["CleanHome", "PrimeHouse", "SparklePro"],
    "Stationery": ["PaperTrail", "SchoolDesk", "WriteWell"],
}


def money(value: float | int | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def qty(value: float | int | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def infer_unit_of_measure(product_name: str) -> str:
    lower_name = product_name.lower()
    if "kg" in lower_name:
        return "kg"
    if "500g" in lower_name or "200g" in lower_name or "150g" in lower_name or "100g" in lower_name:
        return "g"
    if "1l" in lower_name or "1lt" in lower_name:
        return "l"
    if "ml" in lower_name:
        return "ml"
    if "pack" in lower_name or "bags" in lower_name:
        return "pack"
    if "box" in lower_name:
        return "box"
    return "pcs"


def generate_seed_barcode(index: int) -> str:
    return f"8902026{index:06d}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed realistic retail demo data.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing demo data before seeding. Use only for local development.",
    )
    return parser.parse_args()


def table_counts(db: Session) -> dict[str, int]:
    return {
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
        "branches": db.scalar(select(func.count()).select_from(Branch)) or 0,
        "products": db.scalar(select(func.count()).select_from(Product)) or 0,
        "sales": db.scalar(select(func.count()).select_from(Sale)) or 0,
        "invoices": db.scalar(select(func.count()).select_from(Invoice)) or 0,
    }


def ensure_empty_or_reset(db: Session, reset: bool) -> None:
    counts = table_counts(db)
    has_data = any(counts.values())
    if has_data and not reset:
        raise RuntimeError(
            "Database already contains data. Re-run with --reset for local development reseeding."
        )

    if not has_data:
        return

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
        Company,
        Supplier,
        Category,
        User,
        Branch,
    ]:
        db.execute(delete(model))
    db.commit()


def create_branches(db: Session) -> list[Branch]:
    branches = [Branch(**branch_data) for branch_data in BRANCHES]
    db.add_all(branches)
    db.flush()
    return branches


def create_business_settings(db: Session, branches: list[Branch]) -> Company:
    company = Company(**DEMO_COMPANY)
    db.add(company)
    db.flush()

    primary_branch = next(branch for branch in branches if branch.name == "Central Market")
    primary_gst = BRANCH_GST_DETAILS[primary_branch.name]
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
            terms_and_conditions="Goods once sold are subject to store return policy. GST details are for demo use.",
        )
    )

    for branch in branches:
        gst_details = BRANCH_GST_DETAILS[branch.name]
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
            TaxRate(name="GST Exempt 0%", rate_percent=money(0), cess_percent=money(0), description="Zero-rated or exempt demo items"),
            TaxRate(name="GST 5%", rate_percent=money(5), cess_percent=money(0), description="Common essential goods GST slab"),
            TaxRate(name="GST 12%", rate_percent=money(12), cess_percent=money(0), description="Standard demo GST slab"),
            TaxRate(name="GST 18%", rate_percent=money(18), cess_percent=money(0), description="General demo GST slab"),
            TaxRate(name="GST 28%", rate_percent=money(28), cess_percent=money(0), description="Higher demo GST slab"),
        ]
    )

    payment_modes = [
        ("Cash", PaymentModeType.CASH, False),
        ("UPI", PaymentModeType.UPI, True),
        ("Card", PaymentModeType.CARD, True),
        ("Bank Transfer", PaymentModeType.BANK_TRANSFER, True),
        ("Credit", PaymentModeType.CREDIT, False),
    ]
    db.add_all(
        [
            PaymentMode(
                company_id=company.id,
                name=name,
                mode_type=mode_type,
                requires_reference=requires_reference,
                display_order=index,
            )
            for index, (name, mode_type, requires_reference) in enumerate(payment_modes, start=1)
        ]
    )

    db.add(
        InvoiceSequence(
            company_id=company.id,
            branch_id=None,
            invoice_type=InvoiceSequenceType.GST_INVOICE,
            fiscal_year="2026-2027",
            prefix="INV-2026-",
            suffix=None,
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
    return company


def create_product_units(db: Session) -> None:
    db.add_all(
        [
            ProductUnit(name=name, symbol=symbol, description=description, is_active=True)
            for name, symbol, description in PRODUCT_UNIT_DEFINITIONS
        ]
    )
    db.flush()


def create_categories(db: Session) -> dict[str, Category]:
    categories = {name: Category(name=name, description=description) for name, description in CATEGORIES}
    db.add_all(categories.values())
    db.flush()
    return categories


def create_suppliers(db: Session) -> dict[str, Supplier]:
    suppliers = {}
    for name, contact, email, phone, lead_time, terms in SUPPLIERS:
        suppliers[name] = Supplier(
            name=name,
            contact_person=contact,
            email=email,
            phone=phone,
            address=f"{SEED_RANDOM.randint(10, 99)} Commerce Park, {SEED_RANDOM.choice(['Bengaluru', 'Delhi', 'Pune', 'Mumbai'])}",
            payment_terms=terms,
            lead_time_days=lead_time,
        )
    db.add_all(suppliers.values())
    db.flush()
    return suppliers


def create_users(db: Session, branches: list[Branch]) -> dict[str, User]:
    password_hash = hash_password(DEMO_PASSWORD)
    users = {
        "admin": User(
            name="Aarav Sharma",
            email="admin@hybridretail.test",
            password_hash=password_hash,
            role=UserRole.ADMIN,
        ),
        "central_manager": User(
            name="Ananya Rao",
            email="manager.central@hybridretail.test",
            password_hash=hash_password(DEMO_PASSWORD),
            role=UserRole.STORE_MANAGER,
            branch_id=branches[0].id,
        ),
        "north_staff": User(
            name="Kabir Verma",
            email="staff.north@hybridretail.test",
            password_hash=hash_password(DEMO_PASSWORD),
            role=UserRole.STAFF,
            branch_id=branches[1].id,
        ),
        "lakeside_staff": User(
            name="Diya Iyer",
            email="staff.lakeside@hybridretail.test",
            password_hash=hash_password(DEMO_PASSWORD),
            role=UserRole.STAFF,
            branch_id=branches[2].id,
        ),
        "analyst": User(
            name="Nisha Kapoor",
            email="analyst@hybridretail.test",
            password_hash=hash_password(DEMO_PASSWORD),
            role=UserRole.ANALYST,
        ),
    }
    db.add_all(users.values())
    db.flush()
    return users


def create_customers(db: Session, branches: list[Branch], users: dict[str, User]) -> list[Customer]:
    company = db.scalar(select(Company).order_by(Company.id))
    payment_modes = {mode.name: mode for mode in db.scalars(select(PaymentMode)).all()}
    branches_by_name = {branch.name: branch for branch in branches}
    customers: list[Customer] = []

    for index, (name, phone, email, gstin, branch_name, state, state_code, credit_limit, opening_balance, notes) in enumerate(CUSTOMERS, start=1):
        branch = branches_by_name[branch_name]
        address = f"{SEED_RANDOM.randint(10, 99)} Customer Street, {branch.city}"
        customer = Customer(
            company_id=company.id if company else None,
            branch_id=branch.id,
            name=name,
            phone=phone,
            email=email,
            gstin=gstin,
            billing_address=address,
            shipping_address=address if index % 3 else f"{SEED_RANDOM.randint(10, 99)} Delivery Lane, {branch.city}",
            city=branch.city,
            state=state,
            state_code=state_code,
            pincode=BRANCH_GST_DETAILS[branch.name]["pincode"],
            credit_limit=money(credit_limit),
            opening_balance=money(opening_balance),
            is_active=True,
        )
        db.add(customer)
        db.flush()
        customers.append(customer)

        for address_type, address_value in [
            (CustomerAddressType.BILLING, customer.billing_address),
            (CustomerAddressType.SHIPPING, customer.shipping_address),
        ]:
            db.add(
                CustomerAddress(
                    customer_id=customer.id,
                    address_type=address_type,
                    recipient_name=customer.name,
                    phone=customer.phone,
                    address=address_value,
                    city=customer.city,
                    state=customer.state,
                    state_code=customer.state_code,
                    pincode=customer.pincode,
                    gstin=customer.gstin,
                    is_default=True,
                )
            )

        if customer.opening_balance > 0:
            opening_datetime = datetime.combine(END_DATE - timedelta(days=75 + index), time(hour=9), tzinfo=UTC)
            db.add(
                CustomerLedgerEntry(
                    customer_id=customer.id,
                    branch_id=customer.branch_id,
                    entry_type=CustomerLedgerEntryType.OPENING_BALANCE,
                    debit=customer.opening_balance,
                    credit=Decimal("0.00"),
                    reference_type="seed_opening_balance",
                    reference_id=None,
                    reason="Seeded opening receivable",
                    notes=notes,
                    created_by=users["admin"].id,
                    entry_datetime=opening_datetime,
                    created_at=opening_datetime,
                )
            )

            if index % 2 == 0:
                payment_amount = money(customer.opening_balance * Decimal(str(SEED_RANDOM.uniform(0.25, 0.55))))
                payment_datetime = datetime.combine(END_DATE - timedelta(days=SEED_RANDOM.randint(3, 45)), time(hour=16), tzinfo=UTC)
                payment_mode = payment_modes[SEED_RANDOM.choice(["Cash", "UPI", "Bank Transfer"])]
                payment = CustomerPayment(
                    customer_id=customer.id,
                    branch_id=customer.branch_id,
                    payment_mode_id=payment_mode.id,
                    amount=payment_amount,
                    payment_datetime=payment_datetime,
                    reference_number=f"RCPT-SEED-{index:04d}",
                    notes="Seeded customer payment",
                    received_by=users["admin"].id,
                )
                db.add(payment)
                db.flush()
                ledger_entry = CustomerLedgerEntry(
                    customer_id=customer.id,
                    branch_id=customer.branch_id,
                    entry_type=CustomerLedgerEntryType.PAYMENT,
                    debit=Decimal("0.00"),
                    credit=payment.amount,
                    reference_type="customer_payment",
                    reference_id=payment.id,
                    reason="Seeded payment receipt",
                    notes=payment.notes,
                    created_by=users["admin"].id,
                    entry_datetime=payment.payment_datetime,
                    created_at=payment.payment_datetime,
                )
                db.add(ledger_entry)
                db.flush()
                payment.ledger_entry_id = ledger_entry.id

    db.flush()
    return customers


def create_products(
    db: Session,
    categories: dict[str, Category],
    suppliers: dict[str, Supplier],
) -> list[Product]:
    tax_rates = {tax_rate.name: tax_rate for tax_rate in db.scalars(select(TaxRate)).all()}
    products: list[Product] = []
    product_index = 1
    for category_name, items in PRODUCT_CATALOG.items():
        for name, sku, supplier_name, cost, price, threshold, target, _velocity in items:
            tax_rate = tax_rates[CATEGORY_TAX_RATE_NAMES[category_name]]
            selling_price = money(price)
            product = Product(
                sku=sku,
                name=name,
                description=f"{name} from {category_name.lower()} category",
                category_id=categories[category_name].id,
                supplier_id=suppliers[supplier_name].id,
                gst_rate_id=tax_rate.id,
                unit_cost=money(cost),
                selling_price=selling_price,
                hsn_sac_code=CATEGORY_HSN_CODES[category_name],
                cess_rate_percent=money(0),
                primary_barcode=generate_seed_barcode(product_index),
                unit_of_measure=infer_unit_of_measure(name),
                mrp=money(selling_price * Decimal("1.08")),
                brand=CATEGORY_BRANDS[category_name][(product_index - 1) % len(CATEGORY_BRANDS[category_name])],
                manufacturer=supplier_name,
                item_type=ProductItemType.GOODS.value,
                batch_tracking_enabled=category_name == "Dairy",
                serial_tracking_enabled=False,
                expiry_tracking_enabled=category_name in {"Dairy", "Beverages", "Snacks"},
                reorder_threshold=qty(threshold),
                target_stock_level=qty(target),
            )
            products.append(product)
            product_index += 1
    db.add_all(products)
    db.flush()
    for product in products:
        if product.primary_barcode:
            db.add(
                ProductBarcode(
                    product_id=product.id,
                    barcode=product.primary_barcode,
                    barcode_type="primary",
                    is_primary=True,
                    is_active=True,
                )
            )
        db.add(
            ProductPriceHistory(
                product_id=product.id,
                old_unit_cost=None,
                new_unit_cost=product.unit_cost,
                old_selling_price=None,
                new_selling_price=product.selling_price,
                old_mrp=None,
                new_mrp=product.mrp,
                changed_by=None,
                reason="Seeded retail catalog pricing",
            )
        )
    db.flush()
    return products


def product_velocity_map() -> dict[str, str]:
    return {
        sku: velocity
        for items in PRODUCT_CATALOG.values()
        for _name, sku, _supplier, _cost, _price, _threshold, _target, velocity in items
    }


def create_inventory(db: Session, branches: list[Branch], products: list[Product]) -> dict[tuple[int, int], Inventory]:
    velocity_by_sku = product_velocity_map()
    inventory_by_key: dict[tuple[int, int], Inventory] = {}
    low_stock_skus = {"DRY-MLK-1LT", "BEV-WTR-1LT", "SNK-CHP-052", "GRC-SGR-1KG", "HHD-DTG-1KG"}
    zero_stock_skus = {"DRY-CRD-500", "SNK-CHO-040", "PCR-TOP-150"}
    on_order_skus = {"DRY-MLK-1LT", "BEV-WTR-1LT", "HHD-DTG-1KG", "GRC-OIL-1LT", "STN-A4P-500"}

    for product in products:
        velocity = velocity_by_sku[product.sku]
        for branch_index, branch in enumerate(branches):
            branch_multiplier = Decimal(str([1.05, 0.88, 0.72][branch_index]))
            if product.sku in zero_stock_skus and branch_index == 1:
                on_hand = Decimal("0")
            elif product.sku in low_stock_skus:
                on_hand = product.reorder_threshold - Decimal(SEED_RANDOM.randint(1, 6))
            elif velocity == "fast":
                on_hand = product.target_stock_level * branch_multiplier * Decimal(str(SEED_RANDOM.uniform(0.55, 0.95)))
            elif velocity == "seasonal":
                on_hand = product.target_stock_level * branch_multiplier * Decimal(str(SEED_RANDOM.uniform(0.35, 0.85)))
            elif velocity == "slow":
                on_hand = product.target_stock_level * branch_multiplier * Decimal(str(SEED_RANDOM.uniform(1.05, 1.9)))
            else:
                on_hand = product.target_stock_level * branch_multiplier * Decimal(str(SEED_RANDOM.uniform(0.65, 1.25)))

            on_order = Decimal("0")
            if product.sku in on_order_skus and branch_index != 2:
                on_order = product.reorder_threshold + Decimal(SEED_RANDOM.randint(10, 35))

            inventory = Inventory(
                product_id=product.id,
                branch_id=branch.id,
                quantity_on_hand=max(qty(on_hand), Decimal("0")),
                quantity_reserved=qty(SEED_RANDOM.randint(0, 6)),
                quantity_on_order=qty(on_order),
            )
            db.add(inventory)
            if product.batch_tracking_enabled or product.expiry_tracking_enabled:
                shelf_life_days = 14 if product.sku.startswith("DRY-") else 120
                db.add(
                    InventoryBatch(
                        product_id=product.id,
                        branch_id=branch.id,
                        batch_number=f"B-{product.sku}-{branch.id}-001",
                        expiry_date=END_DATE + timedelta(days=shelf_life_days),
                        mrp=product.mrp,
                        quantity_on_hand=inventory.quantity_on_hand,
                        is_active=True,
                    )
                )
            inventory_by_key[(product.id, branch.id)] = inventory

    db.flush()
    return inventory_by_key


def demand_weight(product: Product) -> float:
    velocity = product_velocity_map()[product.sku]
    base = {
        "fast": 6.2,
        "steady": 3.1,
        "seasonal": 2.8,
        "slow": 0.8,
    }[velocity]
    if product.category and product.category.name in {"Dairy", "Snacks", "Beverages"}:
        base *= 1.15
    return base


def seasonal_multiplier(day: date, product: Product) -> float:
    month = day.month
    category_name = product.category.name if product.category else ""
    if category_name in {"Beverages", "Dairy"} and month in {3, 4, 5}:
        return 1.25
    if category_name == "Stationery" and month in {6, 7, 8}:
        return 1.35
    if category_name == "Household" and month in {10, 11}:
        return 1.2
    if day.weekday() >= 5:
        return 1.18
    return 1.0


def create_sales(
    db: Session,
    branches: list[Branch],
    products: list[Product],
    users: dict[str, User],
) -> None:
    weighted_products = [(product, demand_weight(product)) for product in products]
    staff_by_branch = {
        branches[0].id: users["central_manager"].id,
        branches[1].id: users["north_staff"].id,
        branches[2].id: users["lakeside_staff"].id,
    }
    sale_counter = 1
    stock_movements: list[StockMovement] = []

    current_day = START_DATE
    while current_day <= END_DATE:
        for branch_index, branch in enumerate(branches):
            branch_factor = [1.15, 0.95, 0.78][branch_index]
            weekday_factor = 1.25 if current_day.weekday() >= 5 else 0.9
            trend_factor = 1 + ((current_day - START_DATE).days / 270) * 0.12
            transaction_count = max(
                2,
                int(SEED_RANDOM.gauss(8.5 * branch_factor * weekday_factor * trend_factor, 2.0)),
            )

            for _ in range(transaction_count):
                sale_datetime = datetime.combine(
                    current_day,
                    time(
                        hour=SEED_RANDOM.randint(9, 21),
                        minute=SEED_RANDOM.choice([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]),
                    ),
                    tzinfo=UTC,
                )
                item_count = SEED_RANDOM.choices([1, 2, 3, 4], weights=[48, 32, 15, 5], k=1)[0]
                product_pool = [product for product, _weight in weighted_products]
                demand_weights = []
                for product, weight in weighted_products:
                    if current_day >= RECENT_SLOW_MOVING_CUTOFF and product.sku in RECENTLY_INACTIVE_SKUS:
                        demand_weights.append(0)
                    else:
                        demand_weights.append(weight * seasonal_multiplier(current_day, product))
                chosen_products = SEED_RANDOM.choices(product_pool, weights=demand_weights, k=item_count)

                subtotal = Decimal("0")
                sale = Sale(
                    sale_number=f"SAL-{current_day.strftime('%Y%m%d')}-{sale_counter:05d}",
                    branch_id=branch.id,
                    sale_datetime=sale_datetime,
                    subtotal=Decimal("0"),
                    discount_total=Decimal("0"),
                    tax_total=Decimal("0"),
                    total_amount=Decimal("0"),
                    created_by=staff_by_branch[branch.id],
                    created_at=sale_datetime,
                )
                db.add(sale)
                db.flush()

                for product in chosen_products:
                    velocity = product_velocity_map()[product.sku]
                    max_qty = 4 if velocity == "fast" else 2
                    quantity = qty(SEED_RANDOM.randint(1, max_qty))
                    discount = money(product.selling_price * quantity * Decimal(str(SEED_RANDOM.choice([0, 0, 0, 0.03, 0.05]))))
                    line_total = money(product.selling_price * quantity - discount)
                    subtotal += line_total
                    db.add(
                        SaleItem(
                            sale_id=sale.id,
                            product_id=product.id,
                            quantity=quantity,
                            unit_price=product.selling_price,
                            discount_amount=discount,
                            line_total=line_total,
                        )
                    )
                    stock_movements.append(
                        StockMovement(
                            product_id=product.id,
                            branch_id=branch.id,
                            movement_type=StockMovementType.SALE,
                            quantity_change=-quantity,
                            reason="Historical seeded sale",
                            reference_type="sale",
                            reference_id=sale.id,
                            created_by=staff_by_branch[branch.id],
                            created_at=sale_datetime,
                        )
                    )

                sale.subtotal = money(subtotal)
                sale.discount_total = Decimal("0")
                sale.tax_total = money(subtotal * Decimal("0.05"))
                sale.total_amount = money(sale.subtotal + sale.tax_total)
                sale_counter += 1

        current_day += timedelta(days=1)

    db.add_all(stock_movements)
    db.flush()


def create_purchase_orders(
    db: Session,
    branches: list[Branch],
    products: list[Product],
    users: dict[str, User],
) -> None:
    products_by_supplier: dict[int, list[Product]] = defaultdict(list)
    for product in products:
        products_by_supplier[product.supplier_id].append(product)

    supplier_ids = list(products_by_supplier.keys())
    statuses = [
        PurchaseOrderStatus.DRAFT,
        PurchaseOrderStatus.PENDING_APPROVAL,
        PurchaseOrderStatus.APPROVED,
        PurchaseOrderStatus.ORDERED,
        PurchaseOrderStatus.PARTIALLY_RECEIVED,
        PurchaseOrderStatus.RECEIVED,
        PurchaseOrderStatus.CANCELLED,
    ]
    po_count = 36
    received_movements: list[StockMovement] = []

    for index in range(1, po_count + 1):
        supplier_id = SEED_RANDOM.choice(supplier_ids)
        branch = SEED_RANDOM.choice(branches)
        status = statuses[index % len(statuses)]
        order_date = END_DATE - timedelta(days=SEED_RANDOM.randint(2, 160))
        expected_delivery_date = order_date + timedelta(days=SEED_RANDOM.randint(2, 10))
        created_by = users["admin"].id if index % 3 else users["central_manager"].id
        approved_by = users["admin"].id if status not in {PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.PENDING_APPROVAL} else None
        approved_at = (
            datetime.combine(order_date + timedelta(days=1), time(hour=11), tzinfo=UTC)
            if approved_by
            else None
        )
        purchase_order = PurchaseOrder(
            po_number=f"PO-{order_date.strftime('%Y%m')}-{index:04d}",
            supplier_id=supplier_id,
            branch_id=branch.id,
            status=status,
            order_date=order_date,
            expected_delivery_date=expected_delivery_date,
            total_amount=Decimal("0"),
            created_by=created_by,
            approved_by=approved_by,
            approved_at=approved_at,
        )
        db.add(purchase_order)
        db.flush()

        total_amount = Decimal("0")
        line_products = SEED_RANDOM.sample(
            products_by_supplier[supplier_id],
            k=min(SEED_RANDOM.randint(2, 5), len(products_by_supplier[supplier_id])),
        )
        for product in line_products:
            quantity_ordered = qty(SEED_RANDOM.randint(12, 80))
            if status == PurchaseOrderStatus.RECEIVED:
                quantity_received = quantity_ordered
            elif status == PurchaseOrderStatus.PARTIALLY_RECEIVED:
                quantity_received = qty(quantity_ordered * Decimal(str(SEED_RANDOM.uniform(0.35, 0.75))))
            else:
                quantity_received = Decimal("0")

            line_total = money(quantity_ordered * product.unit_cost)
            total_amount += line_total
            db.add(
                PurchaseOrderItem(
                    purchase_order_id=purchase_order.id,
                    product_id=product.id,
                    quantity_ordered=quantity_ordered,
                    quantity_received=quantity_received,
                    unit_cost=product.unit_cost,
                    line_total=line_total,
                )
            )

            if quantity_received > 0:
                received_movements.append(
                    StockMovement(
                        product_id=product.id,
                        branch_id=branch.id,
                        movement_type=StockMovementType.PURCHASE_RECEIVED,
                        quantity_change=quantity_received,
                        reason="Seeded purchase order receipt",
                        reference_type="purchase_order",
                        reference_id=purchase_order.id,
                        created_by=users["admin"].id,
                        created_at=datetime.combine(
                            min(expected_delivery_date, END_DATE),
                            time(hour=15),
                            tzinfo=UTC,
                        ),
                    )
                )

        purchase_order.total_amount = money(total_amount)

    db.add_all(received_movements)
    db.flush()


def create_demo_invoices(db: Session, branches: list[Branch], users: dict[str, User]) -> None:
    from app.schemas.invoices import InvoiceCreate, InvoiceIssueRequest, InvoiceItemCreate, InvoicePaymentCreate
    from app.services.invoices import create_draft_invoice_record, issue_invoice_record

    cash_mode = db.scalar(select(PaymentMode).where(PaymentMode.mode_type == PaymentModeType.CASH))
    if cash_mode is None:
        return

    admin = users["admin"]
    candidate_rows = db.execute(
        select(Product, Inventory, Branch)
        .join(Inventory, Inventory.product_id == Product.id)
        .join(Branch, Branch.id == Inventory.branch_id)
        .where(Product.is_active.is_(True), Inventory.quantity_on_hand >= Decimal("8.00"))
        .order_by(Branch.id, Product.name)
        .limit(4)
    ).all()
    if len(candidate_rows) < 2:
        return

    first_product, first_inventory, first_branch = candidate_rows[0]
    second_product, second_inventory, second_branch = candidate_rows[1]
    first_state = BRANCH_GST_DETAILS[first_branch.name]
    cash_payload = InvoiceCreate(
        branch_id=first_branch.id,
        customer_id=None,
        invoice_type="gst",
        place_of_supply_state=first_state["state"],
        place_of_supply_state_code=first_state["state_code"],
        invoice_date=datetime.combine(END_DATE, time(hour=11), tzinfo=UTC),
        items=[
            InvoiceItemCreate(
                product_id=first_product.id,
                quantity=Decimal("1.00"),
                discount=Decimal("0.00"),
            )
        ],
    )
    cash_invoice = create_draft_invoice_record(db, payload=cash_payload, user=admin, request=None)
    issue_invoice_record(
        db,
        invoice=cash_invoice,
        payload=InvoiceIssueRequest(
            payments=[
                InvoicePaymentCreate(
                    payment_mode_id=cash_mode.id,
                    amount=cash_invoice.grand_total,
                    reference_number="SEED-CASH-001",
                    notes="Seeded paid POS invoice",
                )
            ],
            notes="Seeded paid POS invoice",
        ),
        user=admin,
        request=None,
    )

    customer = db.scalar(
        select(Customer)
        .where(
            Customer.branch_id == second_branch.id,
            Customer.is_active.is_(True),
            Customer.credit_limit >= Decimal("500.00"),
            (Customer.credit_limit - Customer.opening_balance) >= Decimal("500.00"),
        )
        .order_by(Customer.credit_limit.desc(), Customer.id)
    )
    if customer is None:
        return
    credit_payload = InvoiceCreate(
        branch_id=second_branch.id,
        customer_id=customer.id,
        invoice_type="gst",
        place_of_supply_state=customer.state,
        place_of_supply_state_code=customer.state_code,
        invoice_date=datetime.combine(END_DATE, time(hour=16), tzinfo=UTC),
        items=[
            InvoiceItemCreate(
                product_id=second_product.id,
                quantity=Decimal("1.00"),
                discount=Decimal("0.00"),
            )
        ],
    )
    credit_invoice = create_draft_invoice_record(db, payload=credit_payload, user=admin, request=None)
    issue_invoice_record(
        db,
        invoice=credit_invoice,
        payload=InvoiceIssueRequest(payments=[], notes="Seeded customer credit invoice"),
        user=admin,
        request=None,
    )
    db.flush()


def create_audit_logs(db: Session, users: dict[str, User]) -> None:
    db.add_all(
        [
            AuditLog(
                user_id=users["admin"].id,
                action="seed_database",
                entity_type="database",
                entity_id=None,
                new_value_json={"seeded_at": datetime.now(UTC).isoformat()},
                ip_address="127.0.0.1",
                notes="Development sample data loaded",
            ),
            AuditLog(
                user_id=users["admin"].id,
                action="create_demo_users",
                entity_type="users",
                entity_id=None,
                new_value_json={"roles": ["admin", "store_manager", "staff", "analyst"]},
                ip_address="127.0.0.1",
                notes="Demo credentials are documented for local development only",
            ),
        ]
    )


def seed_database(reset: bool) -> dict[str, int | str]:
    SEED_RANDOM.seed(SEED_VALUE)
    with SessionLocal() as db:
        ensure_empty_or_reset(db, reset=reset)
        branches = create_branches(db)
        create_business_settings(db, branches)
        create_product_units(db)
        categories = create_categories(db)
        suppliers = create_suppliers(db)
        users = create_users(db, branches)
        create_customers(db, branches, users)
        products = create_products(db, categories, suppliers)
        create_inventory(db, branches, products)
        create_sales(db, branches, products, users)
        create_purchase_orders(db, branches, products, users)
        create_demo_invoices(db, branches, users)
        create_audit_logs(db, users)
        db.commit()

        counts = {
            "branches": db.scalar(select(func.count()).select_from(Branch)) or 0,
            "companies": db.scalar(select(func.count()).select_from(Company)) or 0,
            "tax_rates": db.scalar(select(func.count()).select_from(TaxRate)) or 0,
            "payment_modes": db.scalar(select(func.count()).select_from(PaymentMode)) or 0,
            "customers": db.scalar(select(func.count()).select_from(Customer)) or 0,
            "customer_ledger_entries": db.scalar(select(func.count()).select_from(CustomerLedgerEntry)) or 0,
            "customer_payments": db.scalar(select(func.count()).select_from(CustomerPayment)) or 0,
            "product_units": db.scalar(select(func.count()).select_from(ProductUnit)) or 0,
            "categories": db.scalar(select(func.count()).select_from(Category)) or 0,
            "suppliers": db.scalar(select(func.count()).select_from(Supplier)) or 0,
            "products": db.scalar(select(func.count()).select_from(Product)) or 0,
            "product_barcodes": db.scalar(select(func.count()).select_from(ProductBarcode)) or 0,
            "inventory_batches": db.scalar(select(func.count()).select_from(InventoryBatch)) or 0,
            "inventory_records": db.scalar(select(func.count()).select_from(Inventory)) or 0,
            "invoices": db.scalar(select(func.count()).select_from(Invoice)) or 0,
            "invoice_items": db.scalar(select(func.count()).select_from(InvoiceItem)) or 0,
            "invoice_taxes": db.scalar(select(func.count()).select_from(InvoiceTax)) or 0,
            "invoice_payments": db.scalar(select(func.count()).select_from(InvoicePayment)) or 0,
            "sales": db.scalar(select(func.count()).select_from(Sale)) or 0,
            "sale_items": db.scalar(select(func.count()).select_from(SaleItem)) or 0,
            "purchase_orders": db.scalar(select(func.count()).select_from(PurchaseOrder)) or 0,
            "users": db.scalar(select(func.count()).select_from(User)) or 0,
        }
        counts["history_start"] = START_DATE.isoformat()
        counts["history_end"] = END_DATE.isoformat()
        return counts


def main() -> None:
    args = parse_args()
    summary = seed_database(reset=args.reset)
    print("Seed complete:")
    for key, value in summary.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
