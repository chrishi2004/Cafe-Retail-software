from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import BranchScope, get_branch_scope, get_scope_context, require_reporting_access
from app.db.session import get_db
from app.models import User
from app.core.scope import ScopeContext
from app.schemas.ai import AIChatRequest, AIChatResponse, AIChatSessionDetailRead, AIChatSessionRead
from app.services.ai import get_chat_session_detail, query_chat_sessions, run_ai_chat

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=AIChatResponse)
def chat(
    payload: AIChatRequest,
    current_user: Annotated[User, Depends(require_reporting_access)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> AIChatResponse:
    return run_ai_chat(db, payload=payload, user=current_user, branch_scope=branch_scope, scope=scope)


@router.get("/sessions", response_model=list[AIChatSessionRead])
def list_ai_sessions(
    current_user: Annotated[User, Depends(require_reporting_access)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
) -> list[AIChatSessionRead]:
    return query_chat_sessions(db, user=current_user, limit=limit)


@router.get("/sessions/{session_id}", response_model=AIChatSessionDetailRead)
def get_ai_session(
    session_id: int,
    current_user: Annotated[User, Depends(require_reporting_access)],
    db: Annotated[Session, Depends(get_db)],
) -> AIChatSessionDetailRead:
    return get_chat_session_detail(db, session_id=session_id, user=current_user)
