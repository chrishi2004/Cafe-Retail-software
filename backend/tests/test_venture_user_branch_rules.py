from sqlalchemy.orm import Session, sessionmaker

from app.core.scope import scope_context_for_user
from app.models import User, UserRole
from tests.multi_venture_fixtures import TEST_PASSWORD, login_headers, seed_two_ventures


def test_operational_role_without_branch_is_rejected_at_creation(client, db_session_factory: sessionmaker[Session]) -> None:
    seed_two_ventures(db_session_factory)
    owner_headers = login_headers(client, "owner@example.test")
    response = client.post(
        "/api/venture-users",
        headers=owner_headers,
        json={
            "name": "Branchless Kitchen",
            "email": "branchless.kitchen@example.com",
            "password": TEST_PASSWORD,
            "role": "kitchen",
            "company_id": 2,
            "branch_id": None,
        },
    )
    assert response.status_code == 400


def test_company_wide_admin_rejects_branch_assignment(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_two_ventures(db_session_factory)
    owner_headers = login_headers(client, "owner@example.test")
    response = client.post(
        "/api/venture-users",
        headers=owner_headers,
        json={
            "name": "Branch Bound Admin",
            "email": "branch.admin@example.com",
            "password": TEST_PASSWORD,
            "role": "admin",
            "company_id": 2,
            "branch_id": ids["cafe_branch"],
        },
    )
    assert response.status_code == 400


def test_invalid_legacy_branchless_operational_user_fails_closed(client, db_session_factory: sessionmaker[Session]) -> None:
    seed_two_ventures(db_session_factory)
    with db_session_factory() as db:
        cafe = db.get(User, 1)
        assert cafe is not None
        invalid = User(
            business_group_id=1,
            company_id=2,
            branch_id=None,
            name="Invalid Branchless Staff",
            email="invalid.branchless.staff@example.test",
            password_hash=cafe.password_hash,
            role=UserRole.STAFF,
        )
        db.add(invalid)
        db.commit()
        scope = scope_context_for_user(invalid)
        assert scope.branch_ids == (-1,)

    response = client.post(
        "/api/auth/login",
        json={"email": "invalid.branchless.staff@example.test", "password": TEST_PASSWORD},
    )
    assert response.status_code == 401


def test_retail_and_cafe_reject_roles_from_the_other_workspace(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_two_ventures(db_session_factory)
    owner_headers = login_headers(client, "owner@example.test")

    cafe_staff = client.post(
        "/api/venture-users",
        headers=owner_headers,
        json={
            "name": "Wrong Cafe Staff Role",
            "email": "wrong.cafe.staff@example.com",
            "password": TEST_PASSWORD,
            "role": "staff",
            "company_id": 2,
            "branch_id": ids["cafe_branch"],
        },
    )
    assert cafe_staff.status_code == 400

    retail_kitchen = client.post(
        "/api/venture-users",
        headers=owner_headers,
        json={
            "name": "Wrong Retail Kitchen Role",
            "email": "wrong.retail.kitchen@example.com",
            "password": TEST_PASSWORD,
            "role": "kitchen",
            "company_id": 1,
            "branch_id": ids["retail_branch"],
        },
    )
    assert retail_kitchen.status_code == 400


def test_invalid_legacy_cross_workspace_role_fails_closed_at_login(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_two_ventures(db_session_factory)
    with db_session_factory() as db:
        template = db.get(User, 1)
        assert template is not None
        invalid = User(
            business_group_id=1,
            company_id=2,
            branch_id=ids["cafe_branch"],
            name="Invalid Legacy Cafe Staff",
            email="invalid.legacy.cafe.staff@example.test",
            password_hash=template.password_hash,
            role=UserRole.STAFF,
        )
        db.add(invalid)
        db.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": "invalid.legacy.cafe.staff@example.test", "password": TEST_PASSWORD},
    )
    assert response.status_code == 401
