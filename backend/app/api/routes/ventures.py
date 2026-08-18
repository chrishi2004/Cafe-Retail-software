from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_scope_context, require_roles
from app.api.errors import raise_bad_request, raise_conflict, raise_not_found
from app.core.scope import BRANCH_REQUIRED_ROLES, ScopeContext
from app.core.security import hash_password
from app.db.session import get_db
from app.models import Branch, BusinessType, Company, User, UserRole
from app.schemas.ventures import VentureRead, VentureUserCreate, VentureUserRead, VentureUserUpdate
from app.services.audit import write_audit_log

router = APIRouter(tags=["ventures"])

SuperAdmin = Annotated[User, Depends(require_roles(UserRole.SUPER_ADMIN))]
CurrentScope = Annotated[ScopeContext, Depends(get_scope_context)]


def _load_company(db: Session, company_id: int) -> Company:
    company = db.get(Company, company_id, execution_options={"scope_bypass": True})
    if company is None or not company.is_active:
        raise_not_found("Venture not found.")
    return company


def _validate_assignment(db: Session, *, role: UserRole, company_id: int | None, branch_id: int | None) -> None:
    if role == UserRole.SUPER_ADMIN:
        if company_id is not None or branch_id is not None:
            raise_bad_request("Super Admin cannot be assigned to a venture or branch.")
        return
    if company_id is None:
        raise_bad_request("A venture assignment is required for this role.")
    company = _load_company(db, company_id)
    allowed_roles = (
        {UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.ORDER_TAKER, UserRole.KITCHEN, UserRole.ANALYST}
        if company.business_type == BusinessType.CAFE
        else {UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.STAFF, UserRole.ANALYST}
    )
    if role not in allowed_roles:
        raise_bad_request("The selected role is not supported by this venture type.")

    if role in BRANCH_REQUIRED_ROLES and branch_id is None:
        raise_bad_request("This operational role requires a branch assignment.")
    if role == UserRole.ADMIN and branch_id is not None:
        raise_bad_request("Venture Admin is company-wide and cannot be assigned to one branch.")

    if branch_id is not None:
        branch = db.get(Branch, branch_id, execution_options={"scope_bypass": True})
        if branch is None or branch.company_id != company_id or not branch.is_active:
            raise_bad_request("Branch does not belong to the selected venture.")


@router.get("/ventures/current", response_model=VentureRead | None)
def current_venture(scope: CurrentScope, db: Annotated[Session, Depends(get_db)]) -> Company | None:
    if scope.all_companies:
        return None
    if scope.company_id is None:
        raise_not_found("Venture not found.")
    company = db.get(Company, scope.company_id)
    if company is None:
        raise_not_found("Venture not found.")
    return company


@router.get("/ventures", response_model=list[VentureRead])
def list_ventures(_owner: SuperAdmin, db: Annotated[Session, Depends(get_db)]) -> list[Company]:
    statement = (
        select(Company)
        .where(Company.is_active.is_(True))
        .order_by(Company.name)
        .execution_options(scope_bypass=True)
    )
    return list(db.scalars(statement).all())


@router.get("/venture-users", response_model=list[VentureUserRead])
def list_venture_users(
    _owner: SuperAdmin,
    db: Annotated[Session, Depends(get_db)],
    company_id: Annotated[int | None, Query()] = None,
) -> list[User]:
    statement = select(User).order_by(User.name)
    if company_id is not None:
        _load_company(db, company_id)
        statement = statement.where(User.company_id == company_id)
    return list(db.scalars(statement.execution_options(scope_bypass=True)).all())


@router.post("/venture-users", response_model=VentureUserRead, status_code=status.HTTP_201_CREATED)
def create_venture_user(
    payload: VentureUserCreate,
    request: Request,
    owner: SuperAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    _validate_assignment(db, role=payload.role, company_id=payload.company_id, branch_id=payload.branch_id)
    existing = db.scalar(
        select(User)
        .where(func.lower(User.email) == payload.email.lower())
        .execution_options(scope_bypass=True)
    )
    if existing is not None:
        raise_conflict("A user with this email already exists.")

    user = User(
        business_group_id=owner.business_group_id,
        company_id=payload.company_id,
        branch_id=payload.branch_id,
        name=payload.name.strip(),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    write_audit_log(
        db,
        action="venture_user.created",
        entity_type="user",
        entity_id=user.id,
        user=owner,
        company_id=payload.company_id,
        new_value_json={
            "email": user.email,
            "role": user.role.value,
            "company_id": user.company_id,
            "branch_id": user.branch_id,
        },
        request=request,
    )
    db.commit()
    db.refresh(user)
    return user


@router.put("/venture-users/{user_id}", response_model=VentureUserRead)
def update_venture_user_assignment(
    user_id: int,
    payload: VentureUserUpdate,
    request: Request,
    owner: SuperAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user = db.get(User, user_id, execution_options={"scope_bypass": True})
    if user is None or user.business_group_id != owner.business_group_id:
        raise_not_found("User not found.")
    if user.id == owner.id and (payload.role != UserRole.SUPER_ADMIN or not payload.is_active):
        raise_bad_request("The current Super Admin cannot remove or deactivate their own global access.")
    _validate_assignment(db, role=payload.role, company_id=payload.company_id, branch_id=payload.branch_id)

    old = {
        "role": user.role.value,
        "company_id": user.company_id,
        "branch_id": user.branch_id,
        "is_active": user.is_active,
        "token_version": user.token_version,
    }
    user.role = payload.role
    user.company_id = payload.company_id
    user.branch_id = payload.branch_id
    user.is_active = payload.is_active
    user.token_version += 1
    write_audit_log(
        db,
        action="venture_user.assignment_updated",
        entity_type="user",
        entity_id=user.id,
        user=owner,
        company_id=payload.company_id,
        old_value_json=old,
        new_value_json={
            "role": user.role.value,
            "company_id": user.company_id,
            "branch_id": user.branch_id,
            "is_active": user.is_active,
            "token_version": user.token_version,
        },
        request=request,
    )
    db.commit()
    db.refresh(user)
    return user
