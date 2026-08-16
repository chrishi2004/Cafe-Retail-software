from sqlalchemy.orm import Session, sessionmaker

from app.models import User
from tests.multi_venture_fixtures import TEST_PASSWORD, login_headers, seed_two_ventures


def test_cafe_partner_auth_me_is_cafe_only(client, db_session_factory: sessionmaker[Session]) -> None:
    seed_two_ventures(db_session_factory)
    headers = login_headers(client, "cafe.admin@example.test")
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["company_business_type"] == "cafe"
    assert me.json()["company_id"] == 2
    assert me.json()["role"] == "admin"
    assert client.get("/api/ventures", headers=headers).status_code == 403
    assert client.get("/api/venture-users", headers=headers).status_code == 403


def test_super_admin_can_select_retail_cafe_or_all_scope(client, db_session_factory: sessionmaker[Session]) -> None:
    seed_two_ventures(db_session_factory)
    owner_headers = login_headers(client, "owner@example.test")

    ventures = client.get("/api/ventures", headers=owner_headers)
    assert ventures.status_code == 200
    assert {row["business_type"] for row in ventures.json()} == {"retail", "cafe"}

    all_products = client.get("/api/products", headers=owner_headers)
    assert {row["name"] for row in all_products.json()} == {"Retail Secret Product", "Cafe Product"}

    cafe_headers = {**owner_headers, "X-Venture-Id": "2"}
    cafe_products = client.get("/api/products", headers=cafe_headers)
    assert cafe_products.status_code == 200
    assert {row["name"] for row in cafe_products.json()} == {"Cafe Product"}
    current = client.get("/api/ventures/current", headers=cafe_headers)
    assert current.status_code == 200
    assert current.json()["business_type"] == "cafe"


def test_super_admin_creates_company_scoped_user_and_assignment_change_revokes_token(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_two_ventures(db_session_factory)
    owner_headers = login_headers(client, "owner@example.test")

    created = client.post(
        "/api/venture-users",
        headers=owner_headers,
        json={
            "name": "Cafe Kitchen Two",
            "email": "cafe.kitchen2@example.com",
            "password": TEST_PASSWORD,
            "role": "kitchen",
            "company_id": 2,
            "branch_id": ids["cafe_branch"],
        },
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]
    old_headers = login_headers(client, "cafe.kitchen2@example.com")

    updated = client.put(
        f"/api/venture-users/{user_id}",
        headers=owner_headers,
        json={
            "role": "staff",
            "company_id": 1,
            "branch_id": ids["retail_branch"],
            "is_active": True,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["company_id"] == 1
    assert updated.json()["role"] == "staff"
    assert client.get("/api/auth/me", headers=old_headers).status_code == 401


def test_user_assignment_rejects_branch_from_other_venture(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_two_ventures(db_session_factory)
    owner_headers = login_headers(client, "owner@example.test")
    response = client.post(
        "/api/venture-users",
        headers=owner_headers,
        json={
            "name": "Invalid Cafe Manager",
            "email": "invalid.cafe.manager@example.com",
            "password": TEST_PASSWORD,
            "role": "store_manager",
            "company_id": 2,
            "branch_id": ids["retail_branch"],
        },
    )
    assert response.status_code == 400


def test_normal_admin_cannot_create_or_reassign_users(client, db_session_factory: sessionmaker[Session]) -> None:
    seed_two_ventures(db_session_factory)
    admin_headers = login_headers(client, "admin@hybridretail.test")
    response = client.post(
        "/api/venture-users",
        headers=admin_headers,
        json={
            "name": "Unauthorized User",
            "email": "unauthorized@example.com",
            "password": TEST_PASSWORD,
            "role": "staff",
            "company_id": 1,
        },
    )
    assert response.status_code == 403


def test_cafe_seed_accounts_can_be_single_company_users(
    db_session_factory: sessionmaker[Session],
    seed_auth_data: None,
) -> None:
    ids = seed_two_ventures(db_session_factory)
    with db_session_factory() as db:
        cafe_admin = db.get(User, ids["cafe_admin"])
        assert cafe_admin is not None
        assert cafe_admin.company_id == 2
        assert cafe_admin.business_group_id == 1
