from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.errors import raise_conflict, raise_not_found
from app.db.session import get_db
from app.models import Category, User
from app.schemas.master_data import CategoryCreate, CategoryRead, CategoryUpdate
from app.services.audit import write_audit_log

router = APIRouter(prefix="/categories", tags=["categories"])


def ensure_category_name_available(db: Session, name: str, category_id: int | None = None) -> None:
    existing = db.scalar(select(Category).where(Category.name == name))
    if existing is not None and existing.id != category_id:
        raise_conflict("Category name already exists.")


def get_category_or_404(db: Session, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise_not_found("Category not found.")
    return category


@router.get("", response_model=list[CategoryRead])
def list_categories(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
) -> list[Category]:
    statement = select(Category).order_by(Category.name)
    if search:
        statement = statement.where(Category.name.ilike(f"%{search.strip()}%"))
    return list(db.scalars(statement).all())


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    request: Request,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Category:
    ensure_category_name_available(db, payload.name)
    category = Category(**payload.model_dump())
    db.add(category)
    db.flush()
    write_audit_log(
        db,
        action="category.create",
        entity_type="category",
        entity_id=category.id,
        user=_admin,
        new_value_json=payload.model_dump(),
        request=request,
    )
    db.commit()
    db.refresh(category)
    return category


@router.put("/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    request: Request,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Category:
    category = get_category_or_404(db, category_id)
    ensure_category_name_available(db, payload.name, category_id=category.id)
    old_value = {"name": category.name, "description": category.description}
    for field, value in payload.model_dump().items():
        setattr(category, field, value)
    write_audit_log(
        db,
        action="category.update",
        entity_type="category",
        entity_id=category.id,
        user=_admin,
        old_value_json=old_value,
        new_value_json=payload.model_dump(),
        request=request,
    )
    db.commit()
    db.refresh(category)
    return category
