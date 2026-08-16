from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.errors import raise_conflict, raise_not_found
from app.db.session import get_db
from app.models import Supplier, User
from app.schemas.master_data import SupplierCreate, SupplierRead, SupplierUpdate
from app.services.audit import write_audit_log

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def ensure_supplier_name_available(db: Session, name: str, supplier_id: int | None = None) -> None:
    existing = db.scalar(select(Supplier).where(Supplier.name == name))
    if existing is not None and existing.id != supplier_id:
        raise_conflict("Supplier name already exists.")


def get_supplier_or_404(db: Session, supplier_id: int) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise_not_found("Supplier not found.")
    return supplier


@router.get("", response_model=list[SupplierRead])
def list_suppliers(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    include_inactive: bool = False,
) -> list[Supplier]:
    statement = select(Supplier).order_by(Supplier.name)
    if not include_inactive:
        statement = statement.where(Supplier.is_active.is_(True))
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            Supplier.name.ilike(term) | Supplier.contact_person.ilike(term) | Supplier.email.ilike(term)
        )
    return list(db.scalars(statement).all())


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    request: Request,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Supplier:
    ensure_supplier_name_available(db, payload.name)
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.flush()
    write_audit_log(
        db,
        action="supplier.create",
        entity_type="supplier",
        entity_id=supplier.id,
        user=_admin,
        new_value_json=payload.model_dump(),
        request=request,
    )
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get("/{supplier_id}", response_model=SupplierRead)
def get_supplier(
    supplier_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Supplier:
    return get_supplier_or_404(db, supplier_id)


@router.put("/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    request: Request,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Supplier:
    supplier = get_supplier_or_404(db, supplier_id)
    ensure_supplier_name_available(db, payload.name, supplier_id=supplier.id)
    old_value = SupplierRead.model_validate(supplier).model_dump()
    for field, value in payload.model_dump().items():
        setattr(supplier, field, value)
    write_audit_log(
        db,
        action="supplier.update",
        entity_type="supplier",
        entity_id=supplier.id,
        user=_admin,
        old_value_json=old_value,
        new_value_json=payload.model_dump(),
        request=request,
    )
    db.commit()
    db.refresh(supplier)
    return supplier
