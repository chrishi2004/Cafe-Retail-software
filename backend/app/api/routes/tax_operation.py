from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_scope_context, require_roles
from app.core.scope import ScopeContext
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.tax_operation import (
    CombinedTurnoverRead,
    GSTActivationRequest,
    TaxOperationRead,
    TaxOperationSettingsUpdate,
)
from app.services.tax_operation import (
    activate_gst_operation,
    combined_turnover,
    get_tax_operation,
    update_tax_operation_settings,
)

router = APIRouter(prefix="/tax-operation", tags=["tax-operation"])


@router.get("", response_model=TaxOperationRead)
def read_tax_operation(
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> TaxOperationRead:
    return get_tax_operation(db, scope=scope)


@router.put("/settings", response_model=TaxOperationRead)
def update_tax_settings(
    payload: TaxOperationSettingsUpdate,
    request: Request,
    owner: Annotated[User, Depends(require_roles(UserRole.SUPER_ADMIN))],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> TaxOperationRead:
    return update_tax_operation_settings(
        db,
        scope=scope,
        payload=payload,
        user=owner,
        request=request,
    )


@router.post("/activate-gst", response_model=TaxOperationRead)
def activate_gst(
    payload: GSTActivationRequest,
    request: Request,
    owner: Annotated[User, Depends(require_roles(UserRole.SUPER_ADMIN))],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> TaxOperationRead:
    return activate_gst_operation(
        db,
        scope=scope,
        payload=payload,
        user=owner,
        request=request,
    )


@router.get("/combined-turnover", response_model=CombinedTurnoverRead)
def read_combined_turnover(
    _owner: Annotated[User, Depends(require_roles(UserRole.SUPER_ADMIN))],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> CombinedTurnoverRead:
    return combined_turnover(db, scope=scope)
