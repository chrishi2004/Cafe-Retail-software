from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class ProductionInstallation(TimestampMixin, Base):
    __tablename__ = 'production_installations'
    id: Mapped[int] = mapped_column(primary_key=True)
    installation_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    __table_args__ = (CheckConstraint('id = 1', name='singleton'),)
