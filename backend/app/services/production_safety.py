"""Fail closed before demo writers or reset helpers can touch production data."""
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session


def assert_demo_seed_allowed(db: Session) -> None:
    from app.core.config import settings
    from app.models import Company
    if settings.environment.lower() in {'production', 'prod'}:
        raise RuntimeError('Demo seed/reset is disabled in production. Use the new-install bootstrap only.')
    tables = set(inspect(db.get_bind()).get_table_names())
    if 'production_installations' in tables and db.execute(text('SELECT 1 FROM production_installations LIMIT 1')).first():
        raise RuntimeError('Demo seed/reset refused: this database is a production installation.')
    if 'companies' in tables and db.scalar(select(Company.id).where(Company.is_demo.is_(False)).limit(1)):
        raise RuntimeError('Demo seed/reset refused: non-demo business data exists.')
