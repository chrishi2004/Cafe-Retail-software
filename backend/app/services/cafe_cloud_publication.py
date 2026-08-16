from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.errors import raise_bad_request
from app.models import (
    Branch,
    BusinessType,
    CafeTable,
    Company,
    Inventory,
    MenuCategory,
    MenuItem,
    TableQRToken,
)
from app.schemas.cloud import (
    AvailabilityInput,
    MenuPublicationInput,
    PublishedCategoryInput,
    PublishedItemInput,
    PublishedTableInput,
)


def build_cafe_publication(
    db: Session,
    *,
    company_id: int,
    branch_id: int,
    version: int,
    publication_id: UUID | None = None,
    snapshot_at: datetime | None = None,
) -> MenuPublicationInput:
    company = db.get(Company, company_id, execution_options={"scope_bypass": True})
    branch = db.get(Branch, branch_id, execution_options={"scope_bypass": True})
    if (
        company is None
        or not company.is_active
        or company.business_type != BusinessType.CAFE
        or branch is None
        or not branch.is_active
        or branch.company_id != company.id
    ):
        raise_bad_request("Active Cafe company and branch are required for cloud publication.")

    categories = list(
        db.scalars(
            select(MenuCategory)
            .where(
                MenuCategory.company_id == company.id,
                MenuCategory.is_active.is_(True),
                or_(MenuCategory.branch_id.is_(None), MenuCategory.branch_id == branch.id),
            )
            .execution_options(scope_bypass=True)
            .order_by(MenuCategory.display_order, MenuCategory.name, MenuCategory.id)
        ).all()
    )
    category_ids = {row.id for row in categories}
    category_public_ids = {row.id: row.public_id for row in categories}
    items = list(
        db.scalars(
            select(MenuItem)
            .where(
                MenuItem.company_id == company.id,
                MenuItem.is_active.is_(True),
                MenuItem.category_id.in_(category_ids or {-1}),
                or_(MenuItem.branch_id.is_(None), MenuItem.branch_id == branch.id),
            )
            .execution_options(scope_bypass=True)
            .order_by(MenuItem.display_order, MenuItem.name, MenuItem.id)
        ).all()
    )
    tables = list(
        db.scalars(
            select(CafeTable)
            .where(
                CafeTable.company_id == company.id,
                CafeTable.branch_id == branch.id,
                CafeTable.is_active.is_(True),
            )
            .execution_options(scope_bypass=True)
            .order_by(CafeTable.table_code, CafeTable.id)
        ).all()
    )

    now = snapshot_at or datetime.now(UTC)
    published_tables: list[PublishedTableInput] = []
    for table in tables:
        qr = db.scalar(
            select(TableQRToken)
            .where(
                TableQRToken.company_id == company.id,
                TableQRToken.branch_id == branch.id,
                TableQRToken.table_id == table.id,
                TableQRToken.revoked_at.is_(None),
                or_(TableQRToken.expires_at.is_(None), TableQRToken.expires_at > now),
            )
            .execution_options(scope_bypass=True)
            .order_by(TableQRToken.created_at.desc(), TableQRToken.id.desc())
        )
        if qr is None:
            continue
        published_tables.append(
            PublishedTableInput(
                source_table_id=str(table.id),
                table_code=table.table_code,
                table_display_name=table.display_name,
                public_reference=qr.public_reference,
                verifier_digest=qr.token_hash,
                valid_until=qr.expires_at,
                disabled_at=qr.revoked_at,
                available=True,
            )
        )

    linked_product_ids = sorted({row.product_id for row in items if row.product_id is not None})
    availability: list[AvailabilityInput] = []
    for product_id in linked_product_ids:
        quantity = db.scalar(
            select(func.coalesce(func.sum(Inventory.quantity_on_hand), 0))
            .where(
                Inventory.company_id == company.id,
                Inventory.branch_id == branch.id,
                Inventory.product_id == product_id,
            )
            .execution_options(scope_bypass=True)
        )
        availability.append(
            AvailabilityInput(source_product_id=str(product_id), available=bool(quantity and quantity > 0))
        )

    return MenuPublicationInput(
        publication_id=publication_id or uuid4(),
        business_group_id=str(company.business_group_id),
        company_id=str(company.id),
        branch_id=str(branch.id),
        version=version,
        snapshot_at=now,
        categories=[
            PublishedCategoryInput(
                source_category_id=row.public_id,
                name=row.name,
                display_order=row.display_order,
                is_active=row.is_active,
            )
            for row in categories
        ],
        items=[
            PublishedItemInput(
                source_menu_item_id=row.public_id,
                source_product_id=str(row.product_id) if row.product_id is not None else None,
                source_category_id=category_public_ids[row.category_id],
                name=row.name,
                description=row.description,
                image_reference=row.image_reference,
                selling_price=row.selling_price,
                preparation_area=row.preparation_area.value,
                available=row.available,
                display_order=row.display_order,
            )
            for row in items
        ],
        tables=published_tables,
        availability=availability,
    )