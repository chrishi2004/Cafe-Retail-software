from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.errors import raise_conflict, raise_not_found
from app.db.session import get_db
from app.models import Branch, User
from app.schemas.master_data import BranchCreate, BranchRead, BranchUpdate
from app.services.audit import write_audit_log

router = APIRouter(prefix="/branches", tags=["branches"])


def ensure_branch_name_available(db: Session, name: str, branch_id: int | None = None) -> None:
    existing = db.scalar(select(Branch).where(Branch.name == name))
    if existing is not None and existing.id != branch_id:
        raise_conflict("Branch name already exists.")


def get_branch_or_404(db: Session, branch_id: int) -> Branch:
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise_not_found("Branch not found.")
    return branch


@router.get("", response_model=list[BranchRead])
def list_branches(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    include_inactive: bool = False,
) -> list[Branch]:
    statement = select(Branch).order_by(Branch.name)
    if not include_inactive:
        statement = statement.where(Branch.is_active.is_(True))
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            Branch.name.ilike(term) | Branch.city.ilike(term) | Branch.manager_name.ilike(term)
        )
    return list(db.scalars(statement).all())


@router.post("", response_model=BranchRead, status_code=status.HTTP_201_CREATED)
def create_branch(
    payload: BranchCreate,
    request: Request,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Branch:
    ensure_branch_name_available(db, payload.name)
    branch = Branch(**payload.model_dump())
    db.add(branch)
    db.flush()
    write_audit_log(
        db,
        action="branch.create",
        entity_type="branch",
        entity_id=branch.id,
        user=_admin,
        new_value_json=payload.model_dump(),
        request=request,
    )
    db.commit()
    db.refresh(branch)
    return branch


@router.put("/{branch_id}", response_model=BranchRead)
def update_branch(
    branch_id: int,
    payload: BranchUpdate,
    request: Request,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Branch:
    branch = get_branch_or_404(db, branch_id)
    ensure_branch_name_available(db, payload.name, branch_id=branch.id)
    old_value = BranchRead.model_validate(branch).model_dump()
    for field, value in payload.model_dump().items():
        setattr(branch, field, value)
    write_audit_log(
        db,
        action="branch.update",
        entity_type="branch",
        entity_id=branch.id,
        user=_admin,
        old_value_json=old_value,
        new_value_json=payload.model_dump(),
        request=request,
    )
    db.commit()
    db.refresh(branch)
    return branch
