from sqlalchemy.orm import Session, sessionmaker

from app.models import Company, User
from tests.multi_venture_fixtures import login_headers, seed_two_ventures


def test_auth_me_returns_server_derived_company_scope(client, db_session_factory: sessionmaker[Session]) -> None:
    seed_two_ventures(db_session_factory)
    headers = login_headers(client, "cafe.admin@example.test")

    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["company_id"] == 2
    assert payload["business_group_id"] == 1
    assert payload["role"] == "admin"
    assert "venture.manage" in payload["permissions"]


def test_token_version_change_revokes_existing_access_token(client, db_session_factory: sessionmaker[Session]) -> None:
    headers = login_headers(client, "admin@hybridretail.test")
    with db_session_factory() as db:
        user = db.query(User).filter(User.email == "admin@hybridretail.test").one()
        user.token_version += 1
        db.commit()

    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401


def test_deactivated_company_fails_closed_at_login(client, db_session_factory: sessionmaker[Session]) -> None:
    seed_two_ventures(db_session_factory)
    with db_session_factory() as db:
        company = db.get(Company, 2)
        assert company is not None
        company.is_active = False
        db.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": "cafe.admin@example.test", "password": "RetailDemo@123"},
    )
    assert response.status_code == 401


def test_logout_persists_revocation_via_token_version(client, db_session_factory: sessionmaker[Session]) -> None:
    headers = login_headers(client, "admin@hybridretail.test")
    before = None
    with db_session_factory() as db:
        before = db.query(User).filter(User.email == "admin@hybridretail.test").one().token_version

    response = client.post("/api/auth/logout", headers=headers)
    assert response.status_code == 200

    with db_session_factory() as db:
        after = db.query(User).filter(User.email == "admin@hybridretail.test").one().token_version
    assert after == before + 1
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_step_up_is_persisted_and_wrong_password_fails(client, db_session_factory: sessionmaker[Session]) -> None:
    headers = login_headers(client, "admin@hybridretail.test")
    bad = client.post("/api/auth/step-up", headers=headers, json={"password": "wrong"})
    assert bad.status_code == 401

    good = client.post("/api/auth/step-up", headers=headers, json={"password": "RetailDemo@123"})
    assert good.status_code == 200
    with db_session_factory() as db:
        user = db.query(User).filter(User.email == "admin@hybridretail.test").one()
        assert user.last_step_up_at is not None
