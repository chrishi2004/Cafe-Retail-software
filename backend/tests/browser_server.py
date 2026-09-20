"""Disposable real-HTTP browser fixture. No production database is touched."""
import os
import tempfile
from pathlib import Path

if os.environ.get('BROWSER_FIXTURE') != '1' or os.environ.get('ENVIRONMENT') != 'test':
    raise RuntimeError('Browser fixture requires BROWSER_FIXTURE=1 and ENVIRONMENT=test.')

import uvicorn
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import Settings
from app.db.base import Base
from app.db.scoping import ScopedSession
from app.db.session import get_db
from app.main import create_app
from tests.conftest import seed_auth_data
from tests.p8_fixtures import seed_p8


def main():
    with tempfile.TemporaryDirectory(prefix='cafe-browser-') as directory:
        engine = create_engine(f'sqlite:///{Path(directory) / "fixture.db"}', connect_args={'check_same_thread': False})
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, class_=ScopedSession, expire_on_commit=False)
        seed_auth_data.__wrapped__(factory)
        seed_p8(factory)
        app = create_app(Settings(_env_file=None, environment='test', deployment_mode='local_hub',
                                  frontend_origin='http://127.0.0.1:4174', require_privileged_mfa=False))
        def database():
            with factory() as db:
                yield db
        app.dependency_overrides[get_db] = database
        try:
            uvicorn.run(app, host='127.0.0.1', port=8001)
        finally:
            engine.dispose()


if __name__ == '__main__':
    main()
