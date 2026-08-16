from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Callable

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.errors import raise_forbidden, raise_unauthorized
from app.core.scope import (
    BRANCH_REQUIRED_ROLES,
    ScopeContext,
    has_permission,
    scope_context_for_user,
)
from app.core.security import (
    TokenError,
    decode_access_token,
    is_access_token_invalidated,
)
from app.db.scoping import bind_scope
from app.db.session import get_db
from app.models import BusinessGroup, Company, User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    user: User
    scope: ScopeContext
    token: str
    token_id: str
    token_expires_at_timestamp: int
    token_expires_at: datetime
    payload: dict[str, object]


@dataclass(frozen=True)
class BranchScope:
    all_branches: bool
    branch_ids: list[int]


def get_auth_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    x_venture_id: Annotated[int | None, Header(alias="X-Venture-Id")] = None,
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise_unauthorized()

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except TokenError:
        raise_unauthorized("Invalid or expired access token.")

    token_id = str(payload["jti"])
    if is_access_token_invalidated(token_id):
        raise_unauthorized("Access token has been logged out.")

    try:
        user_id = int(str(payload["sub"]))
        expires_at_timestamp = int(payload["exp"])
        token_version = int(payload["ver"])
    except (KeyError, TypeError, ValueError):
        raise_unauthorized("Invalid access token.")

    # Authentication happens before request scope is bound, so these ownership
    # records are loaded explicitly from the trusted server-side user row.
    user = db.get(User, user_id, execution_options={"scope_bypass": True})
    if user is None or not user.is_active:
        raise_unauthorized("User account is inactive or no longer exists.")
    if token_version != user.token_version:
        raise_unauthorized("Access token has been revoked.")

    group = db.get(
        BusinessGroup,
        user.business_group_id,
        execution_options={"scope_bypass": True},
    )
    if group is None or not group.is_active:
        raise_unauthorized("User account is inactive or no longer exists.")

    selected_company_id: int | None = None
    if user.role == UserRole.SUPER_ADMIN:
        if user.company_id is not None or user.branch_id is not None:
            raise_unauthorized("Invalid account scope.")
        if x_venture_id is not None:
            company = db.get(
                Company,
                x_venture_id,
                execution_options={"scope_bypass": True},
            )
            if (
                company is None
                or not company.is_active
                or company.business_group_id != user.business_group_id
            ):
                raise_forbidden("Selected venture is not available to this account.")
            selected_company_id = company.id
    else:
        if user.company_id is None:
            raise_unauthorized("Invalid account scope.")
        if user.role in BRANCH_REQUIRED_ROLES and user.branch_id is None:
            raise_unauthorized("User account has an invalid operational assignment.")
        company = db.get(
            Company,
            user.company_id,
            execution_options={"scope_bypass": True},
        )
        if (
            company is None
            or not company.is_active
            or company.business_group_id != user.business_group_id
        ):
            raise_unauthorized("User account is inactive or no longer exists.")
        if x_venture_id is not None and x_venture_id != user.company_id:
            raise_forbidden("Venture switching is not available to this account.")

    scope = scope_context_for_user(user, selected_company_id=selected_company_id)
    bind_scope(db, scope)

    return AuthContext(
        user=user,
        scope=scope,
        token=token,
        token_id=token_id,
        token_expires_at_timestamp=expires_at_timestamp,
        token_expires_at=datetime.fromtimestamp(expires_at_timestamp, tz=UTC),
        payload=payload,
    )


def get_current_user(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> User:
    return context.user


def get_scope_context(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> ScopeContext:
    return context.scope


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        # Super Admin is the only global role. It may perform venture-admin tasks
        # while scoped routes and services remain company-isolated for everyone else.
        if user.role != UserRole.SUPER_ADMIN and user.role not in allowed_roles:
            allowed = ", ".join(role.value for role in allowed_roles)
            raise_forbidden(f"Requires one of these roles: {allowed}.")
        return user

    return dependency


def require_permission(permission: str) -> Callable[[ScopeContext], ScopeContext]:
    def dependency(scope: Annotated[ScopeContext, Depends(get_scope_context)]) -> ScopeContext:
        if not has_permission(scope, permission):
            raise_forbidden("You do not have permission to perform this action.")
        return scope

    return dependency


def require_admin(user: Annotated[User, Depends(require_roles(UserRole.ADMIN))]) -> User:
    return user


def require_operational_write_access(
    user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.STAFF)),
    ],
) -> User:
    return user


def require_reporting_access(
    user: Annotated[
        User,
        Depends(
            require_roles(
                UserRole.ADMIN,
                UserRole.STORE_MANAGER,
                UserRole.ANALYST,
            )
        ),
    ],
) -> User:
    return user


def get_branch_scope(
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
) -> BranchScope:
    return BranchScope(
        all_branches=scope.all_branches,
        branch_ids=list(scope.branch_ids),
    )


def ensure_branch_access(user: User, branch_id: int) -> None:
    if user.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ANALYST}:
        return
    if user.branch_id != branch_id:
        raise_forbidden("You can only access data for your assigned branch.")
