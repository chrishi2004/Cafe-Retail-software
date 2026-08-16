from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import TableSession, TableSessionStatus
from tests.multi_venture_fixtures import login_headers
from tests.p5_fixtures import seed_p5_test_data


def _create_table(client, headers: dict[str, str], branch_id: int, code: str = "S01") -> dict:
    response = client.post(
        "/api/cafe/tables",
        headers=headers,
        json={
            "branch_id": branch_id,
            "table_code": code,
            "display_name": f"Session {code}",
            "capacity": 4,
            "area": "Indoor",
            "is_active": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_only_one_active_session_and_close_releases_table(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p5_test_data(db_session_factory)
    admin_headers = login_headers(client, "cafe.admin@example.test")
    order_headers = login_headers(client, "cafe.orders@example.test")
    table = _create_table(client, admin_headers, ids["cafe_branch"])

    first = client.post(
        "/api/cafe/table-sessions",
        headers=order_headers,
        json={"table_id": table["id"], "session_type": "dine_in"},
    )
    assert first.status_code == 201, first.text
    session = first.json()
    assert session["status"] == "open"

    second = client.post(
        "/api/cafe/table-sessions",
        headers=order_headers,
        json={"table_id": table["id"], "session_type": "dine_in"},
    )
    assert second.status_code == 409

    active = client.get(f"/api/cafe/tables/{table['id']}/active-session", headers=order_headers)
    assert active.status_code == 200
    assert active.json()["public_id"] == session["public_id"]

    blocked_deactivate = client.post(f"/api/cafe/tables/{table['id']}/deactivate", headers=admin_headers)
    assert blocked_deactivate.status_code == 409

    closed = client.post(
        f"/api/cafe/table-sessions/{session['public_id']}/close",
        headers=order_headers,
        json={"expected_version": session["version"], "cancel": False},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"
    assert closed.json()["closed_by"] is not None

    reopened = client.post(
        "/api/cafe/table-sessions",
        headers=order_headers,
        json={"table_id": table["id"], "session_type": "dine_in"},
    )
    assert reopened.status_code == 201, reopened.text
    assert reopened.json()["public_id"] != session["public_id"]

    with db_session_factory() as db:
        active_count = db.scalar(
            select(func.count()).select_from(TableSession).where(
                TableSession.table_id == table["id"],
                TableSession.status.in_([TableSessionStatus.OPEN, TableSessionStatus.BILL_REQUESTED, TableSessionStatus.BILLED]),
            )
        )
    assert active_count == 1


def test_session_access_is_cafe_role_and_branch_scoped(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_p5_test_data(db_session_factory)
    admin_headers = login_headers(client, "cafe.admin@example.test")
    order_headers = login_headers(client, "cafe.orders@example.test")
    kitchen_headers = login_headers(client, "cafe.kitchen@example.test")
    retail_headers = login_headers(client, "admin@hybridretail.test")
    table = _create_table(client, admin_headers, ids["cafe_branch"], "S02")

    assert client.post(
        "/api/cafe/table-sessions",
        headers=kitchen_headers,
        json={"table_id": table["id"], "session_type": "dine_in"},
    ).status_code == 403
    assert client.post(
        "/api/cafe/table-sessions",
        headers=retail_headers,
        json={"table_id": table["id"], "session_type": "dine_in"},
    ).status_code == 403

    opened = client.post(
        "/api/cafe/table-sessions",
        headers=order_headers,
        json={"table_id": table["id"], "session_type": "dine_in"},
    )
    assert opened.status_code == 201
    public_id = opened.json()["public_id"]
    assert client.get(f"/api/cafe/table-sessions/{public_id}", headers=retail_headers).status_code == 403


def test_stale_close_version_is_rejected(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_p5_test_data(db_session_factory)
    admin_headers = login_headers(client, "cafe.admin@example.test")
    order_headers = login_headers(client, "cafe.orders@example.test")
    table = _create_table(client, admin_headers, ids["cafe_branch"], "S03")
    opened = client.post(
        "/api/cafe/table-sessions",
        headers=order_headers,
        json={"table_id": table["id"], "session_type": "counter"},
    ).json()

    stale = client.post(
        f"/api/cafe/table-sessions/{opened['public_id']}/close",
        headers=order_headers,
        json={"expected_version": opened["version"] + 1, "cancel": False},
    )
    assert stale.status_code == 409
