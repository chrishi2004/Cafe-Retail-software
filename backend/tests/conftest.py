from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.scoping import ScopedSession
from app.db.session import get_db
from app.main import create_app
from app.models import Branch, BusinessGroup, BusinessType, Company, User, UserRole


@pytest.fixture()
def db_session_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(
        class_=ScopedSession,
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False,
    )

    try:
        yield factory
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def seed_auth_data(db_session_factory: sessionmaker[Session]) -> None:
    with db_session_factory() as db:
        group = BusinessGroup(
            id=1,
            name="Test Business Group",
            legal_name="Test Business Group",
        )
        retail_company = Company(
            id=1,
            business_group_id=1,
            business_type=BusinessType.RETAIL,
            slug="retail",
            code="TEST_RETAIL",
            name="Test Retail",
            legal_name="Test Retail Private Limited",
            is_demo=True,
        )
        db.add_all([group, retail_company])
        db.flush()

        central_branch = Branch(
            company_id=retail_company.id,
            name="Central Market",
            address="14 MG Road",
            city="Bengaluru",
            manager_name="Ananya Rao",
        )
        db.add(central_branch)
        db.flush()
        db.add_all(
            [
                User(
                    business_group_id=group.id,
                    company_id=retail_company.id,
                    name="Admin User",
                    email="admin@hybridretail.test",
                    password_hash=hash_password("RetailDemo@123"),
                    role=UserRole.ADMIN,
                ),
                User(
                    business_group_id=group.id,
                    company_id=retail_company.id,
                    name="Store Manager",
                    email="manager@hybridretail.test",
                    password_hash=hash_password("RetailDemo@123"),
                    role=UserRole.STORE_MANAGER,
                    branch_id=central_branch.id,
                ),
                User(
                    business_group_id=group.id,
                    company_id=retail_company.id,
                    name="Staff User",
                    email="staff@hybridretail.test",
                    password_hash=hash_password("RetailDemo@123"),
                    role=UserRole.STAFF,
                    branch_id=central_branch.id,
                ),
                User(
                    business_group_id=group.id,
                    company_id=retail_company.id,
                    name="Analyst User",
                    email="analyst@hybridretail.test",
                    password_hash=hash_password("RetailDemo@123"),
                    role=UserRole.ANALYST,
                ),
            ]
        )
        db.commit()


@pytest.fixture()
def client(
    db_session_factory: sessionmaker[Session],
    seed_auth_data: None,
) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        with db_session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
