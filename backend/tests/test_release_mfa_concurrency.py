import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.api.routes import auth
from app.core.mfa import encrypt_totp_secret, hash_recovery_code, new_totp_secret
from app.core.config import settings
from app.db.base import Base
from app.db.scoping import ScopedSession
from app.models import User


@pytest.fixture()
def db_session_factory():
    url = os.environ.get("RELEASE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RELEASE_TEST_DATABASE_URL is required for PostgreSQL MFA concurrency proof")
    admin = create_engine(url)
    if admin.dialect.name != "postgresql":
        admin.dispose()
        pytest.fail("MFA concurrency proof requires PostgreSQL")
    schema = "mfa_release_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine, class_=ScopedSession, expire_on_commit=False)
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_recovery_code_only_authenticates_one_concurrent_login(client, db_session_factory, monkeypatch):
    code = "release-test-recovery-code"
    with db_session_factory() as db:
        user = db.scalar(select(User).where(User.email == "admin@hybridretail.test"))
        user.mfa_enabled = True
        user.mfa_secret_encrypted = encrypt_totp_secret(new_totp_secret(), settings.secret_key)
        user.mfa_recovery_hashes = [hash_recovery_code(code)]
        db.commit()

    original = auth._verify_login_mfa
    first_inside = Event()
    second_inside = Event()
    start = Barrier(2)

    def verify(user, credentials):
        if not first_inside.is_set():
            first_inside.set()
            # With a row lock, the second read waits until the first commits.
            # Without it, both requests can read the same unconsumed code.
            second_inside.wait(timeout=1)
        else:
            second_inside.set()
        return original(user, credentials)

    monkeypatch.setattr(auth, "_verify_login_mfa", verify)

    def attempt():
        start.wait(timeout=10)
        return client.post("/api/auth/login", json={
            "email": "admin@hybridretail.test",
            "password": "RetailDemo@123",
            "recovery_code": code,
        }).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(attempt) for _ in range(2)]
        statuses = [future.result(timeout=20) for future in futures]
    assert sorted(statuses) == [200, 401]
    with db_session_factory() as db:
        user = db.scalar(select(User).where(User.email == "admin@hybridretail.test"))
        assert user.mfa_recovery_hashes == []
