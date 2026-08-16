from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password, verify_password
from app.models import AuditLog, User
from app.services.audit import write_audit_log


def login(
    client,
    email: str = "admin@hybridretail.test",
    password: str = "RetailDemo@123",
) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_password_hash_verification() -> None:
    password_hash = hash_password("RetailDemo@123")

    assert password_hash != "RetailDemo@123"
    assert verify_password("RetailDemo@123", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_valid_user_can_log_in_without_exposing_password_hash(client) -> None:
    response = client.post(
        "/api/auth/login",
        json={
            "email": "admin@hybridretail.test",
            "password": "RetailDemo@123",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["user"]["email"] == "admin@hybridretail.test"
    assert payload["user"]["role"] == "admin"
    assert "password_hash" not in payload["user"]


def test_invalid_login_fails_clearly_and_is_audited(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    response = client.post(
        "/api/auth/login",
        json={
            "email": "admin@hybridretail.test",
            "password": "bad-password",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "unauthorized",
        "message": "Invalid email or password.",
    }

    with db_session_factory() as db:
        failures = db.scalar(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.action == "auth.login_failure"
            )
        )
    assert failures == 1


def test_me_rejects_unauthenticated_user(client) -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_me_returns_current_user_without_password_hash(client) -> None:
    token = login(client, email="manager@hybridretail.test")

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "manager@hybridretail.test"
    assert payload["role"] == "store_manager"
    assert payload["branch_id"] == 1
    assert "password_hash" not in payload


def test_admin_role_check_allows_admin(client) -> None:
    token = login(client)

    response = client.get(
        "/api/auth/admin-check",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Admin access granted."


def test_admin_role_check_rejects_non_admin(client) -> None:
    token = login(client, email="manager@hybridretail.test")

    response = client.get(
        "/api/auth/admin-check",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_branch_scope_for_manager_is_limited_to_assigned_branch(client) -> None:
    token = login(client, email="manager@hybridretail.test")

    response = client.get(
        "/api/auth/branch-scope",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"all_branches": False, "branch_ids": [1]}


def test_logout_invalidates_current_token(client) -> None:
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    logout_response = client.post("/api/auth/logout", headers=headers)
    me_response = client.get("/api/auth/me", headers=headers)

    assert logout_response.status_code == 200
    assert logout_response.json()["message"] == "Logged out successfully."
    assert me_response.status_code == 401
    assert me_response.json()["error"]["message"] == "Access token has been logged out."


def test_audit_log_utility_writes_records(
    db_session_factory: sessionmaker[Session],
    seed_auth_data: None,
) -> None:
    with db_session_factory() as db:
        admin = db.scalar(select(User).where(User.email == "admin@hybridretail.test"))
        audit_log = write_audit_log(
            db,
            action="test.audit_write",
            entity_type="test",
            user=admin,
            new_value_json={"ok": True},
            ip_address="127.0.0.1",
            commit=True,
        )

        assert audit_log.id is not None
        assert audit_log.user_id == admin.id
        assert audit_log.action == "test.audit_write"
