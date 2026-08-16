from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models import ChatSender


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: int | None = None


class AIToolCallRead(BaseModel):
    name: str
    description: str
    data: dict[str, Any]


class AIChatMessageRead(BaseModel):
    id: int
    session_id: int
    sender: ChatSender
    message: str
    metadata_json: dict[str, Any] | None
    created_at: datetime


class AIChatSessionRead(BaseModel):
    id: int
    user_id: int
    branch_id: int | None
    title: str
    created_at: datetime
    updated_at: datetime
    last_message: str | None = None


class AIChatSessionDetailRead(AIChatSessionRead):
    messages: list[AIChatMessageRead]


class AIChatResponse(BaseModel):
    session_id: int
    intent: str
    response: str
    tool_calls: list[AIToolCallRead]
    requires_confirmation: bool = False
    suggested_action: str | None = None
    user_message: AIChatMessageRead
    assistant_message: AIChatMessageRead
