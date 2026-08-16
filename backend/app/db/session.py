from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import DeploymentMode, settings
from app.db.scoping import ScopedSession

engine_options: dict[str, object] = {"pool_pre_ping": True}
if settings.deployment_mode == DeploymentMode.CLOUD_GATEWAY:
    # Vercel instances are transient; Supabase's transaction pooler owns pooling.
    engine_options.update(
        {
            "poolclass": NullPool,
            "connect_args": {"prepare_threshold": None},
        }
    )

engine = create_engine(settings.runtime_database_url, **engine_options)
SessionLocal = sessionmaker(
    class_=ScopedSession,
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
