from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import BranchScope, ensure_branch_access
from app.api.errors import raise_bad_request, raise_forbidden, raise_not_found
from app.models import (
    Branch,
    Inventory,
    Product,
    Sale,
    SaleItem,
    StockMovement,
    StockMovementType,
    User,
    UserRole,
)
from app.schemas.sales import (
    SaleCreate,
    SaleItemCreate,
    SaleItemRead,
    SaleListItemRead,
    SaleRead,
    SalesSummaryRead,
    SalesTrendPoint,
)
from app.services.audit import write_audit_log

MONEY = Decimal("0.01")
QUANTITY = Decimal("0.01")


@dataclass(frozen=True)
class SalesFilters:
    branch_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    product_id: int | None = None
    category_id: int | None = None
    search: str | None = None
    limit: int = 100


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def quantity(value: Decimal) -> Decimal:
    return value.quantize(QUANTITY, rounding=ROUND_HALF_UP)


def date_bounds(start_date: date | None, end_date: date | None) -> tuple[datetime | None, datetime | None]:
    start = datetime.combine(start_date, time.min, tzinfo=UTC) if start_date else None
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC) if end_date else None
    return start, end


def apply_sales_scope_and_filters(statement, branch_scope: BranchScope, filters: SalesFilters):
    if branch_scope.all_branches:
        if filters.branch_id is not None:
            statement = statement.where(Sale.branch_id == filters.branch_id)
    else:
        if filters.branch_id is not None and filters.branch_id not in branch_scope.branch_ids:
            raise_forbidden("You can only access sales for your assigned branch.")
        statement = statement.where(Sale.branch_id.in_(branch_scope.branch_ids))

    start, end = date_bounds(filters.start_date, filters.end_date)
    if start is not None:
        statement = statement.where(Sale.sale_datetime >= start)
    if end is not None:
        statement = statement.where(Sale.sale_datetime < end)
    if filters.product_id is not None:
        statement = statement.where(Sale.items.any(SaleItem.product_id == filters.product_id))
    if filters.category_id is not None:
        statement = statement.where(
            Sale.items.any(SaleItem.product.has(Product.category_id == filters.category_id))
        )
    if filters.search:
        statement = statement.where(Sale.sale_number.ilike(f"%{filters.search.strip()}%"))

    return statement


def sale_options():
    return (
        joinedload(Sale.branch),
        joinedload(Sale.creator),
        joinedload(Sale.items).joinedload(SaleItem.product),
    )


def sale_item_to_read(item: SaleItem) -> SaleItemRead:
    gross_profit = money((item.unit_price - item.product.unit_cost) * item.quantity - item.discount_amount)
    return SaleItemRead(
        id=item.id,
        product_id=item.product_id,
        product_sku=item.product.sku,
        product_name=item.product.name,
        quantity=item.quantity,
        unit_price=item.unit_price,
        discount_amount=item.discount_amount,
        line_total=item.line_total,
        gross_profit=gross_profit,
    )


def sale_to_list_read(sale: Sale) -> SaleListItemRead:
    items = list(sale.items)
    return SaleListItemRead(
        id=sale.id,
        sale_number=sale.sale_number,
        branch_id=sale.branch_id,
        branch_name=sale.branch.name,
        sale_datetime=sale.sale_datetime,
        subtotal=sale.subtotal,
        discount_total=sale.discount_total,
        tax_total=sale.tax_total,
        total_amount=sale.total_amount,
        gross_profit=sum((sale_item_to_read(item).gross_profit for item in items), Decimal("0.00")),
        units_sold=sum((item.quantity for item in items), Decimal("0.00")),
        item_count=len(items),
        created_by=sale.created_by,
        created_by_name=sale.creator.name,
        created_at=sale.created_at,
    )


def sale_to_read(sale: Sale) -> SaleRead:
    list_read = sale_to_list_read(sale)
    return SaleRead(
        **list_read.model_dump(),
        items=[sale_item_to_read(item) for item in sale.items],
    )


def item_matches_filters(item: SaleItem, filters: SalesFilters) -> bool:
    if filters.product_id is not None and item.product_id != filters.product_id:
        return False
    if filters.category_id is not None and item.product.category_id != filters.category_id:
        return False
    return True


def load_sales(db: Session, *, branch_scope: BranchScope, filters: SalesFilters, apply_limit: bool) -> list[Sale]:
    statement = (
        select(Sale)
        .options(*sale_options())
        .join(Sale.branch)
        .order_by(Sale.sale_datetime.desc(), Sale.id.desc())
    )
    statement = apply_sales_scope_and_filters(statement, branch_scope, filters)
    if apply_limit:
        statement = statement.limit(max(1, min(filters.limit, 500)))
    return list(db.scalars(statement).unique().all())


def query_sales(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: SalesFilters,
) -> list[SaleListItemRead]:
    return [sale_to_list_read(sale) for sale in load_sales(db, branch_scope=branch_scope, filters=filters, apply_limit=True)]


def get_sale_detail(
    db: Session,
    *,
    sale_id: int,
    user: User,
) -> SaleRead:
    sale = db.scalar(select(Sale).options(*sale_options()).where(Sale.id == sale_id))
    if sale is None:
        raise_not_found("Sale not found.")

    ensure_branch_access(user, sale.branch_id)
    return sale_to_read(sale)


def query_sales_summary(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: SalesFilters,
) -> SalesSummaryRead:
    sales = load_sales(db, branch_scope=branch_scope, filters=filters, apply_limit=False)
    revenue = Decimal("0.00")
    gross_profit = Decimal("0.00")
    units_sold = Decimal("0.00")
    transaction_ids: set[int] = set()
    discount_total = Decimal("0.00")
    tax_total = Decimal("0.00")

    for sale in sales:
        matching_items = [item for item in sale.items if item_matches_filters(item, filters)]
        if not matching_items:
            continue
        transaction_ids.add(sale.id)
        line_revenue = sum((item.line_total for item in matching_items), Decimal("0.00"))
        line_discount = sum((item.discount_amount for item in matching_items), Decimal("0.00"))
        revenue += line_revenue
        discount_total += line_discount
        units_sold += sum((item.quantity for item in matching_items), Decimal("0.00"))
        gross_profit += sum(
            ((item.unit_price - item.product.unit_cost) * item.quantity - item.discount_amount for item in matching_items),
            Decimal("0.00"),
        )
        if filters.product_id is None and filters.category_id is None:
            tax_total += sale.tax_total

    transaction_count = len(transaction_ids)
    average_order_value = revenue / transaction_count if transaction_count else Decimal("0.00")
    return SalesSummaryRead(
        revenue=money(revenue),
        gross_profit=money(gross_profit),
        units_sold=quantity(units_sold),
        transaction_count=transaction_count,
        average_order_value=money(average_order_value),
        discount_total=money(discount_total),
        tax_total=money(tax_total),
    )


def query_sales_trends(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: SalesFilters,
) -> list[SalesTrendPoint]:
    sales = load_sales(db, branch_scope=branch_scope, filters=filters, apply_limit=False)
    daily: dict[date, dict[str, Decimal | set[int]]] = defaultdict(
        lambda: {
            "revenue": Decimal("0.00"),
            "gross_profit": Decimal("0.00"),
            "units_sold": Decimal("0.00"),
            "transaction_ids": set(),
        }
    )

    for sale in sales:
        sale_date = sale.sale_datetime.date()
        matching_items = [item for item in sale.items if item_matches_filters(item, filters)]
        if not matching_items:
            continue
        daily[sale_date]["revenue"] += sum((item.line_total for item in matching_items), Decimal("0.00"))
        daily[sale_date]["gross_profit"] += sum(
            ((item.unit_price - item.product.unit_cost) * item.quantity - item.discount_amount for item in matching_items),
            Decimal("0.00"),
        )
        daily[sale_date]["units_sold"] += sum((item.quantity for item in matching_items), Decimal("0.00"))
        transaction_ids = daily[sale_date]["transaction_ids"]
        if isinstance(transaction_ids, set):
            transaction_ids.add(sale.id)

    points: list[SalesTrendPoint] = []
    for sale_date in sorted(daily):
        transaction_ids = daily[sale_date]["transaction_ids"]
        points.append(
            SalesTrendPoint(
                date=sale_date,
                revenue=money(daily[sale_date]["revenue"]),
                gross_profit=money(daily[sale_date]["gross_profit"]),
                units_sold=quantity(daily[sale_date]["units_sold"]),
                transaction_count=len(transaction_ids) if isinstance(transaction_ids, set) else 0,
            )
        )
    return points


def ensure_sale_write_permission(user: User, branch_id: int) -> None:
    if user.role not in {UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.STAFF}:
        raise_forbidden("This role is read-only for sales entry.")
    ensure_branch_access(user, branch_id)


def validate_sale_line(product: Product, item: SaleItemCreate) -> tuple[Decimal, Decimal, Decimal]:
    sold_quantity = quantity(item.quantity)
    unit_price = money(item.unit_price if item.unit_price is not None else product.selling_price)
    discount_amount = money(item.discount_amount)
    line_gross = money(unit_price * sold_quantity)
    if discount_amount > line_gross:
        raise_bad_request(f"Discount cannot exceed line value for {product.sku}.")
    line_total = money(line_gross - discount_amount)
    return sold_quantity, unit_price, line_total


def create_sale(
    db: Session,
    *,
    payload: SaleCreate,
    user: User,
    request: Request,
) -> SaleRead:
    ensure_sale_write_permission(user, payload.branch_id)

    try:
        branch = db.get(Branch, payload.branch_id)
        if branch is None or not branch.is_active:
            raise_not_found("Branch not found.")

        product_ids = {item.product_id for item in payload.items}
        products = {
            product.id: product
            for product in db.scalars(select(Product).where(Product.id.in_(product_ids))).all()
        }
        missing_product_ids = product_ids - products.keys()
        if missing_product_ids:
            raise_not_found("One or more products were not found.")

        requested_by_product: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))
        for item in payload.items:
            product = products[item.product_id]
            if not product.is_active:
                raise_bad_request(f"Inactive product {product.sku} cannot be sold.")
            requested_by_product[item.product_id] += quantity(item.quantity)

        inventories = {
            inventory.product_id: inventory
            for inventory in db.scalars(
                select(Inventory)
                .where(
                    Inventory.branch_id == payload.branch_id,
                    Inventory.product_id.in_(product_ids),
                )
                .with_for_update()
            ).all()
        }

        for product_id, requested_quantity in requested_by_product.items():
            product = products[product_id]
            inventory = inventories.get(product_id)
            if inventory is None:
                raise_bad_request(f"No inventory record exists for {product.sku} at this branch.")
            if inventory.quantity_on_hand < requested_quantity:
                raise_bad_request(
                    f"Insufficient stock for {product.sku}. Available {inventory.quantity_on_hand}, requested {requested_quantity}."
                )

        sale_datetime = payload.sale_datetime or datetime.now(UTC)
        sale = Sale(
            sale_number=f"SAL-{sale_datetime:%Y%m%d}-{uuid4().hex[:8].upper()}",
            branch_id=payload.branch_id,
            sale_datetime=sale_datetime,
            subtotal=Decimal("0.00"),
            discount_total=Decimal("0.00"),
            tax_total=Decimal("0.00"),
            total_amount=Decimal("0.00"),
            created_by=user.id,
        )
        db.add(sale)
        db.flush()

        subtotal = Decimal("0.00")
        discount_total = Decimal("0.00")
        for item in payload.items:
            product = products[item.product_id]
            inventory = inventories[item.product_id]
            sold_quantity, unit_price, line_total = validate_sale_line(product, item)
            discount_amount = money(item.discount_amount)
            subtotal += line_total
            discount_total += discount_amount

            db.add(
                SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    quantity=sold_quantity,
                    unit_price=unit_price,
                    discount_amount=discount_amount,
                    line_total=line_total,
                )
            )

            inventory.quantity_on_hand = quantity(inventory.quantity_on_hand - sold_quantity)
            inventory.last_updated_at = datetime.now(UTC)
            db.add(
                StockMovement(
                    product_id=product.id,
                    branch_id=payload.branch_id,
                    movement_type=StockMovementType.SALE,
                    quantity_change=-sold_quantity,
                    reason=f"Sale {sale.sale_number}",
                    reference_type="sale",
                    reference_id=sale.id,
                    created_by=user.id,
                    created_at=sale_datetime,
                )
            )

        sale.subtotal = money(subtotal)
        sale.discount_total = money(discount_total)
        sale.tax_total = money(sale.subtotal * payload.tax_rate)
        sale.total_amount = money(sale.subtotal + sale.tax_total)
        db.flush()

        write_audit_log(
            db,
            action="sales.create",
            entity_type="sale",
            entity_id=sale.id,
            user=user,
            new_value_json={
                "sale_number": sale.sale_number,
                "branch_id": sale.branch_id,
                "subtotal": str(sale.subtotal),
                "tax_total": str(sale.tax_total),
                "total_amount": str(sale.total_amount),
                "items": [
                    {
                        "product_id": item.product_id,
                        "quantity": str(item.quantity),
                        "discount_amount": str(item.discount_amount),
                    }
                    for item in payload.items
                ],
            },
            request=request,
        )
        sale_id = sale.id
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_sale_detail(db, sale_id=sale_id, user=user)
