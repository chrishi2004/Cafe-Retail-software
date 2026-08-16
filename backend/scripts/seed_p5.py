"""P5 development seed for Cafe menu and table administration.

QR secrets are intentionally NOT pre-generated or printed. Use the authenticated
QR rotation API in development so the raw secret is returned exactly once.
"""

from __future__ import annotations

import argparse
from decimal import Decimal

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models import (
    BusinessType,
    CafeTable,
    Category,
    Company,
    MenuCategory,
    MenuItem,
    PreparationArea,
    Product,
    Supplier,
    TableQRToken,
    TableSession,
)
from scripts.seed_cafe_users import seed_cafe_users
from scripts.seed_p4 import apply_p4_defaults
from scripts.seed_multi_venture import seed_database as seed_multi_venture

MENU_CATEGORIES = [
    "Hot Beverages",
    "Cold Beverages",
    "Snacks",
    "Breakfast",
    "Meals",
    "Desserts",
]

MENU_ITEMS = [
    ("Masala Chai", "Hot Beverages", "35.00", PreparationArea.BEVERAGE),
    ("Ginger Tea", "Hot Beverages", "40.00", PreparationArea.BEVERAGE),
    ("Filter Coffee", "Hot Beverages", "55.00", PreparationArea.BEVERAGE),
    ("Cappuccino", "Hot Beverages", "110.00", PreparationArea.BEVERAGE),
    ("Cold Coffee", "Cold Beverages", "130.00", PreparationArea.BEVERAGE),
    ("Fresh Lime Soda", "Cold Beverages", "85.00", PreparationArea.BEVERAGE),
    ("Iced Tea", "Cold Beverages", "95.00", PreparationArea.BEVERAGE),
    ("Mango Lassi", "Cold Beverages", "120.00", PreparationArea.BEVERAGE),
    ("Veg Samosa", "Snacks", "45.00", PreparationArea.KITCHEN),
    ("Paneer Puff", "Snacks", "75.00", PreparationArea.KITCHEN),
    ("French Fries", "Snacks", "120.00", PreparationArea.KITCHEN),
    ("Veg Sandwich", "Snacks", "140.00", PreparationArea.KITCHEN),
    ("Idli Vada Combo", "Breakfast", "95.00", PreparationArea.KITCHEN),
    ("Masala Dosa", "Breakfast", "125.00", PreparationArea.KITCHEN),
    ("Poha", "Breakfast", "80.00", PreparationArea.KITCHEN),
    ("Aloo Paratha", "Breakfast", "110.00", PreparationArea.KITCHEN),
    ("Veg Thali", "Meals", "190.00", PreparationArea.KITCHEN),
    ("Paneer Rice Bowl", "Meals", "210.00", PreparationArea.KITCHEN),
    ("Veg Pulao", "Meals", "165.00", PreparationArea.KITCHEN),
    ("Dal Khichdi", "Meals", "155.00", PreparationArea.KITCHEN),
    ("Gulab Jamun", "Desserts", "65.00", PreparationArea.COUNTER),
    ("Brownie", "Desserts", "105.00", PreparationArea.COUNTER),
    ("Ice Cream Cup", "Desserts", "90.00", PreparationArea.COUNTER),
    ("Fruit Custard", "Desserts", "95.00", PreparationArea.KITCHEN),
]

PRODUCT_LINK_NAMES = {
    "Masala Chai",
    "Filter Coffee",
    "Cold Coffee",
    "Fresh Lime Soda",
    "Veg Samosa",
    "French Fries",
    "Masala Dosa",
    "Brownie",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed P5 Cafe menu and tables.")
    parser.add_argument("--reset", action="store_true")
    return parser.parse_args()


def clear_p5_data() -> None:
    with SessionLocal() as db:
        for model in [TableSession, TableQRToken, MenuItem, MenuCategory, CafeTable]:
            db.execute(delete(model))
        db.commit()


def _cafe_company_and_branch(db):
    cafe = db.scalar(
        select(Company).where(Company.business_type == BusinessType.CAFE, Company.is_active.is_(True))
    )
    if cafe is None:
        raise RuntimeError("Cafe venture does not exist.")
    from app.models import Branch

    branch = db.scalar(
        select(Branch).where(Branch.company_id == cafe.id, Branch.is_active.is_(True)).order_by(Branch.id)
    )
    if branch is None:
        raise RuntimeError("Cafe branch does not exist.")
    return cafe, branch


def seed_cafe_catalog_and_tables() -> dict[str, int]:
    with SessionLocal() as db:
        cafe, branch = _cafe_company_and_branch(db)

        product_category = db.scalar(
            select(Category).where(Category.company_id == cafe.id, Category.name == "Cafe Sellable Items")
        )
        if product_category is None:
            product_category = Category(
                company_id=cafe.id,
                name="Cafe Sellable Items",
                description="Cafe-owned products used only where a menu item needs inventory linkage.",
            )
            db.add(product_category)
            db.flush()

        supplier = db.scalar(
            select(Supplier).where(Supplier.company_id == cafe.id, Supplier.name == "Cafe Kitchen Supplier")
        )
        if supplier is None:
            supplier = Supplier(
                company_id=cafe.id,
                name="Cafe Kitchen Supplier",
                contact_person="Cafe Procurement",
                email="cafe.supplier@example.com",
                phone="080-4000-5050",
                address="Bengaluru",
                payment_terms="Net 7",
                lead_time_days=2,
                is_active=True,
            )
            db.add(supplier)
            db.flush()

        categories: dict[str, MenuCategory] = {}
        for order, name in enumerate(MENU_CATEGORIES, start=1):
            category = db.scalar(
                select(MenuCategory).where(
                    MenuCategory.company_id == cafe.id,
                    MenuCategory.branch_id.is_(None),
                    MenuCategory.name == name,
                )
            )
            if category is None:
                category = MenuCategory(
                    company_id=cafe.id,
                    branch_id=None,
                    name=name,
                    display_order=order,
                    is_active=True,
                )
                db.add(category)
                db.flush()
            categories[name] = category

        linked_products: dict[str, Product] = {}
        for index, (name, _category, price, _area) in enumerate(MENU_ITEMS, start=1):
            if name not in PRODUCT_LINK_NAMES:
                continue
            sku = f"CAFE-{index:03d}"
            product = db.scalar(
                select(Product).where(Product.company_id == cafe.id, Product.sku == sku)
            )
            if product is None:
                selling_price = Decimal(price)
                product = Product(
                    company_id=cafe.id,
                    sku=sku,
                    name=name,
                    description=f"Cafe-owned product link for {name}",
                    category_id=product_category.id,
                    supplier_id=supplier.id,
                    gst_rate_id=None,
                    unit_cost=(selling_price * Decimal("0.45")).quantize(Decimal("0.01")),
                    selling_price=selling_price,
                    hsn_sac_code=None,
                    cess_rate_percent=Decimal("0.00"),
                    primary_barcode=None,
                    unit_of_measure="serving",
                    mrp=selling_price,
                    brand="Kalpvrik Cafe",
                    manufacturer="Kalpvrik Cafe",
                    item_type="goods",
                    batch_tracking_enabled=False,
                    serial_tracking_enabled=False,
                    expiry_tracking_enabled=False,
                    reorder_threshold=Decimal("0.00"),
                    target_stock_level=Decimal("0.00"),
                    is_active=True,
                )
                db.add(product)
                db.flush()
            linked_products[name] = product

        for order, (name, category_name, price, preparation_area) in enumerate(MENU_ITEMS, start=1):
            item = db.scalar(
                select(MenuItem).where(MenuItem.company_id == cafe.id, MenuItem.name == name)
            )
            if item is None:
                item = MenuItem(
                    company_id=cafe.id,
                    branch_id=None,
                    category_id=categories[category_name].id,
                    product_id=linked_products.get(name).id if name in linked_products else None,
                    name=name,
                    description=f"{name} - P5 development Cafe menu item",
                    image_reference=None,
                    selling_price=Decimal(price),
                    preparation_area=preparation_area,
                    available=True,
                    is_active=True,
                    display_order=order,
                    version=1,
                )
                db.add(item)

        table_specs = [
            ("T01", "Table 1", 2, "Indoor"),
            ("T02", "Table 2", 2, "Indoor"),
            ("T03", "Table 3", 4, "Indoor"),
            ("T04", "Table 4", 4, "Indoor"),
            ("T05", "Table 5", 4, "Indoor"),
            ("T06", "Table 6", 6, "Indoor"),
            ("W01", "Window 1", 2, "Window"),
            ("W02", "Window 2", 2, "Window"),
            ("P01", "Patio 1", 4, "Patio"),
            ("P02", "Patio 2", 4, "Patio"),
            ("P03", "Patio 3", 6, "Patio"),
            ("C01", "Counter 1", 1, "Counter"),
        ]
        for code, display_name, capacity, area in table_specs:
            table = db.scalar(
                select(CafeTable).where(
                    CafeTable.company_id == cafe.id,
                    CafeTable.branch_id == branch.id,
                    CafeTable.table_code == code,
                )
            )
            if table is None:
                db.add(
                    CafeTable(
                        company_id=cafe.id,
                        branch_id=branch.id,
                        table_code=code,
                        display_name=display_name,
                        capacity=capacity,
                        area=area,
                        is_active=True,
                        version=1,
                    )
                )

        db.commit()
        return {
            "menu_categories": len(MENU_CATEGORIES),
            "menu_items": len(MENU_ITEMS),
            "linked_cafe_products": len(linked_products),
            "cafe_tables": len(table_specs),
            "qr_tokens": 0,
        }


def seed_p5(reset: bool) -> dict[str, int]:
    if reset:
        clear_p5_data()
    seed_multi_venture(reset=reset)
    apply_p4_defaults()
    seed_cafe_users()
    return seed_cafe_catalog_and_tables()


def main() -> None:
    args = parse_args()
    summary = seed_p5(reset=args.reset)
    print("P5 Cafe foundation seed complete (QR secrets intentionally not generated):")
    for key, value in summary.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
