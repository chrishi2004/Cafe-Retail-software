from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CompanyScopeMixin, TimestampMixin


class CloudRecordLink(CompanyScopeMixin, TimestampMixin, Base):
    """Durable cross-database identity link created with the local business effect."""

    __tablename__ = "cloud_record_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="cloud_gateway")
    aggregate_type: Mapped[str] = mapped_column(String(80), nullable=False)
    cloud_record_id: Mapped[str] = mapped_column(String(128), nullable=False)
    local_record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    local_public_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_event_id: Mapped[str] = mapped_column(String(36), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "aggregate_type",
            "cloud_record_id",
            name="uq_cloud_record_links_cloud_identity",
        ),
        UniqueConstraint(
            "provider",
            "aggregate_type",
            "local_record_id",
            name="uq_cloud_record_links_local_identity",
        ),
        UniqueConstraint("source_event_id", name="uq_cloud_record_links_source_event"),
        Index("ix_cloud_record_links_company_branch", "company_id", "branch_id"),
        Index("ix_cloud_record_links_cloud", "aggregate_type", "cloud_record_id"),
    )
