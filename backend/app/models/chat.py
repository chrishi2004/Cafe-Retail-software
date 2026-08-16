from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CompanyScopeMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.user import User


class ChatSender(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AIChatSession(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "ai_chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="New chat")

    user: Mapped[User] = relationship(back_populates="ai_chat_sessions")
    branch: Mapped[Branch | None] = relationship(back_populates="ai_chat_sessions")
    messages: Mapped[list[AIChatMessage]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_ai_chat_sessions_company_id", "company_id"),
        Index("ix_ai_chat_sessions_user_id", "user_id"),
    )


class AIChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("ai_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender: Mapped[ChatSender] = mapped_column(
        Enum(
            ChatSender,
            name="chat_sender",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    session: Mapped[AIChatSession] = relationship(back_populates="messages")

    __table_args__ = (Index("ix_ai_chat_messages_session_id", "session_id"),)
