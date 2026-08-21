from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    AuthContext,
    BranchScope,
    get_auth_context,
    get_branch_scope,
    get_current_user,
    get_scope_context,
    require_admin,
)
from app.api.errors import raise_unauthorized
from app.core.config import settings
from app.core.mfa import (
    consume_recovery_code,
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_recovery_codes,
    hash_recovery_code,
    new_totp_secret,
    provisioning_uri,
    verify_totp,
)
from app.core.scope import BRANCH_REQUIRED_ROLES, ScopeContext, scope_context_for_user
from app.core.security import create_access_token, invalidate_access_token, verify_password
from app.db.session import get_db
from app.models import Branch, BusinessGroup, BusinessType, Company, User, UserRole
from app.schemas.auth import (
    BranchScopeResponse,
    LoginRequest,
    MessageResponse,
    MfaConfirmRequest,
    MfaDisableRequest,
    MfaEnrollResponse,
    StepUpRequest,
    TokenResponse,
    UserRead,
)
from app.services.audit import write_audit_log

router = APIRouter(prefix="/auth", tags=["auth"])
PRIVILEGED_MFA_ROLES = {UserRole.SUPER_ADMIN, UserRole.ADMIN}


def _user_read(db: Session, user: User, scope: ScopeContext) -> UserRead:
    company = None
    if user.company_id is not None:
        company = db.get(Company, user.company_id, execution_options={"scope_bypass": True})
    return UserRead(
        id=user.id,
        business_group_id=user.business_group_id,
        company_id=user.company_id,
        company_name=company.name if company else None,
        company_slug=company.slug if company else None,
        company_business_type=company.business_type if company else None,
        name=user.name,
        email=user.email,
        role=user.role,
        branch_id=user.branch_id,
        permissions=sorted(scope.permissions),
        is_active=user.is_active,
        mfa_enabled=user.mfa_enabled,
    )


def _account_scope_is_active(db: Session, user: User) -> bool:
    group = db.get(BusinessGroup, user.business_group_id, execution_options={"scope_bypass": True})
    if group is None or not group.is_active:
        return False
    if user.role == UserRole.SUPER_ADMIN:
        return user.company_id is None and user.branch_id is None
    if user.company_id is None:
        return False
    company = db.get(Company, user.company_id, execution_options={"scope_bypass": True})
    if company is None or not company.is_active or company.business_group_id != user.business_group_id:
        return False
    allowed_roles = (
        {UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.ORDER_TAKER, UserRole.KITCHEN, UserRole.ANALYST}
        if company.business_type == BusinessType.CAFE
        else {UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.STAFF, UserRole.ANALYST}
    )
    if user.role not in allowed_roles:
        return False
    if user.role in BRANCH_REQUIRED_ROLES and user.branch_id is None:
        return False
    if user.role == UserRole.ADMIN and user.branch_id is not None:
        return False
    if user.branch_id is not None:
        branch = db.get(Branch, user.branch_id, execution_options={"scope_bypass": True})
        if branch is None or not branch.is_active or branch.company_id != user.company_id:
            return False
    return True


def _totp_secret(user: User) -> str | None:
    if not user.mfa_secret_encrypted:
        return None
    try:
        return decrypt_totp_secret(user.mfa_secret_encrypted, settings.secret_key)
    except ValueError:
        return None


def _verify_login_mfa(user: User, credentials: LoginRequest) -> bool:
    if not user.mfa_enabled:
        return not (
            settings.resolved_require_privileged_mfa
            and user.role in PRIVILEGED_MFA_ROLES
        )

    secret = _totp_secret(user)
    if secret and credentials.totp_code and verify_totp(secret, credentials.totp_code):
        return True
    if credentials.recovery_code:
        matched, remaining = consume_recovery_code(user.mfa_recovery_hashes, credentials.recovery_code)
        if matched:
            user.mfa_recovery_hashes = remaining
            return True
    return False


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, request: Request, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == credentials.email))
    if user is None or not verify_password(credentials.password, user.password_hash):
        if user is not None:
            user.failed_login_count += 1
        write_audit_log(db, action="auth.login_failure", entity_type="user", entity_id=user.id if user else None, user=user, new_value_json={"email": credentials.email, "success": False}, request=request, notes="Invalid email or password.", commit=True)
        raise_unauthorized("Invalid email or password.")

    if not user.is_active or not _account_scope_is_active(db, user):
        user.failed_login_count += 1
        write_audit_log(db, action="auth.login_failure", entity_type="user", entity_id=user.id, user=user, new_value_json={"email": credentials.email, "success": False}, request=request, notes="Inactive or invalid account scope login attempt.", commit=True)
        raise_unauthorized("User account is inactive.")

    if not _verify_login_mfa(user, credentials):
        user.failed_login_count += 1
        policy_missing = settings.resolved_require_privileged_mfa and user.role in PRIVILEGED_MFA_ROLES and not user.mfa_enabled
        write_audit_log(
            db,
            action="auth.login_failure",
            entity_type="user",
            entity_id=user.id,
            user=user,
            new_value_json={"email": user.email, "success": False, "mfa": True},
            request=request,
            notes="Privileged MFA enrollment required." if policy_missing else "MFA verification failed.",
            commit=True,
        )
        raise_unauthorized(
            "MFA enrollment is required for this privileged account before production login."
            if policy_missing
            else "Authenticator or recovery code is required or invalid."
        )

    user.failed_login_count = 0
    user.last_login_at = datetime.now(UTC)
    access_token, expires_at = create_access_token(subject=user.id, role=user.role.value, token_version=user.token_version)
    write_audit_log(db, action="auth.login_success", entity_type="user", entity_id=user.id, user=user, new_value_json={"email": user.email, "role": user.role.value, "company_id": user.company_id, "success": True, "mfa": user.mfa_enabled}, request=request, commit=True)
    scope = scope_context_for_user(user)
    return TokenResponse(access_token=access_token, expires_at=expires_at, user=_user_read(db, user, scope))


@router.post("/logout", response_model=MessageResponse)
def logout(request: Request, context: Annotated[AuthContext, Depends(get_auth_context)], db: Annotated[Session, Depends(get_db)]) -> MessageResponse:
    invalidate_access_token(context.token_id, context.token_expires_at_timestamp)
    context.user.token_version += 1
    write_audit_log(db, action="auth.logout", entity_type="user", entity_id=context.user.id, user=context.user, new_value_json={"token_id": context.token_id, "token_version": context.user.token_version}, request=request, commit=True)
    return MessageResponse(message="Logged out successfully.")


@router.post("/step-up", response_model=MessageResponse)
def step_up_authentication(payload: StepUpRequest, request: Request, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> MessageResponse:
    valid = verify_password(payload.password, current_user.password_hash)
    if valid and current_user.mfa_enabled:
        secret = _totp_secret(current_user)
        valid = bool(secret and payload.totp_code and verify_totp(secret, payload.totp_code))
    if not valid:
        write_audit_log(db, action="auth.step_up_failure", entity_type="user", entity_id=current_user.id, user=current_user, request=request, notes="Step-up credential/MFA verification failed.", commit=True)
        raise_unauthorized("Invalid credentials.")
    current_user.last_step_up_at = datetime.now(UTC)
    write_audit_log(db, action="auth.step_up_success", entity_type="user", entity_id=current_user.id, user=current_user, new_value_json={"last_step_up_at": current_user.last_step_up_at.isoformat(), "mfa": current_user.mfa_enabled}, request=request, commit=True)
    return MessageResponse(message="Step-up authentication completed.")


@router.post("/mfa/enroll", response_model=MfaEnrollResponse)
def enroll_mfa(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MfaEnrollResponse:
    if current_user.mfa_enabled:
        raise_unauthorized("MFA is already enabled for this account.")
    secret = new_totp_secret()
    recovery_codes = generate_recovery_codes()
    current_user.mfa_secret_encrypted = encrypt_totp_secret(secret, settings.secret_key)
    current_user.mfa_recovery_hashes = [hash_recovery_code(code) for code in recovery_codes]
    current_user.mfa_enrolled_at = None
    write_audit_log(
        db,
        action="auth.mfa_enrollment_started",
        entity_type="user",
        entity_id=current_user.id,
        user=current_user,
        request=request,
        new_value_json={"mfa_enabled": False},
        commit=True,
    )
    return MfaEnrollResponse(
        secret=secret,
        provisioning_uri=provisioning_uri(email=current_user.email, secret=secret),
        recovery_codes=recovery_codes,
    )


@router.post("/mfa/confirm", response_model=MessageResponse)
def confirm_mfa(
    payload: MfaConfirmRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MessageResponse:
    secret = _totp_secret(current_user)
    if not secret or not verify_totp(secret, payload.totp_code):
        write_audit_log(db, action="auth.mfa_confirmation_failure", entity_type="user", entity_id=current_user.id, user=current_user, request=request, notes="TOTP confirmation failed.", commit=True)
        raise_unauthorized("Invalid authenticator code.")
    current_user.mfa_enabled = True
    current_user.mfa_enrolled_at = datetime.now(UTC)
    current_user.token_version += 1
    write_audit_log(
        db,
        action="auth.mfa_enabled",
        entity_type="user",
        entity_id=current_user.id,
        user=current_user,
        request=request,
        new_value_json={"mfa_enabled": True, "token_version": current_user.token_version},
        commit=True,
    )
    return MessageResponse(message="MFA enabled. Sign in again using your authenticator code.")


@router.post("/mfa/disable", response_model=MessageResponse)
def disable_mfa(
    payload: MfaDisableRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MessageResponse:
    secret = _totp_secret(current_user)
    if (
        not current_user.mfa_enabled
        or not verify_password(payload.password, current_user.password_hash)
        or not secret
        or not verify_totp(secret, payload.totp_code)
    ):
        write_audit_log(db, action="auth.mfa_disable_failure", entity_type="user", entity_id=current_user.id, user=current_user, request=request, notes="MFA disable verification failed.", commit=True)
        raise_unauthorized("Invalid credentials.")
    current_user.mfa_enabled = False
    current_user.mfa_secret_encrypted = None
    current_user.mfa_recovery_hashes = None
    current_user.mfa_enrolled_at = None
    current_user.token_version += 1
    write_audit_log(
        db,
        action="auth.mfa_disabled",
        entity_type="user",
        entity_id=current_user.id,
        user=current_user,
        request=request,
        new_value_json={"mfa_enabled": False, "token_version": current_user.token_version},
        commit=True,
    )
    return MessageResponse(message="MFA disabled. Existing sessions were revoked.")


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: Annotated[User, Depends(get_current_user)], scope: Annotated[ScopeContext, Depends(get_scope_context)], db: Annotated[Session, Depends(get_db)]) -> UserRead:
    return _user_read(db, current_user, scope)


@router.get("/admin-check", response_model=MessageResponse)
def admin_check(_admin: Annotated[User, Depends(require_admin)]) -> MessageResponse:
    return MessageResponse(message="Admin access granted.")


@router.get("/branch-scope", response_model=BranchScopeResponse)
def read_branch_scope(branch_scope: Annotated[BranchScope, Depends(get_branch_scope)]) -> BranchScopeResponse:
    return BranchScopeResponse(all_branches=branch_scope.all_branches, branch_ids=branch_scope.branch_ids)
