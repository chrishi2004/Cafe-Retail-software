from sqlalchemy.orm import Session, sessionmaker

from tests.multi_venture_fixtures import login_headers
from tests.p5_fixtures import seed_p5_test_data


def _table_payload(branch_id: int, code: str = "T01") -> dict:
    return {
        "branch_id": branch_id,
        "table_code": code,
        "display_name": f"Table {code}",
        "capacity": 4,
        "area": "Indoor",
        "is_active": True,
    }


def test_cafe_admin_manages_tables_and_duplicate_code_is_branch_scoped(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p5_test_data(db_session_factory)
    headers = login_headers(client, "cafe.admin@example.test")

    first = client.post(
        "/api/cafe/tables",
        headers=headers,
        json=_table_payload(ids["cafe_branch"], "T01"),
    )
    assert first.status_code == 201, first.text
    assert first.json()["table_code"] == "T01"

    duplicate = client.post(
        "/api/cafe/tables",
        headers=headers,
        json=_table_payload(ids["cafe_branch"], "t01"),
    )
    assert duplicate.status_code == 409

    second_branch = client.post(
        "/api/cafe/tables",
        headers=headers,
        json=_table_payload(ids["cafe_second_branch"], "T01"),
    )
    assert second_branch.status_code == 201, second_branch.text
    assert second_branch.json()["branch_id"] == ids["cafe_second_branch"]

    listed = client.get("/api/cafe/tables", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 2


def test_retail_and_non_admin_roles_cannot_administer_cafe_tables(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p5_test_data(db_session_factory)
    retail_headers = login_headers(client, "admin@hybridretail.test")
    cafe_order_headers = login_headers(client, "cafe.orders@example.test")

    assert client.get("/api/cafe/tables", headers=retail_headers).status_code == 403
    assert client.post(
        "/api/cafe/tables",
        headers=retail_headers,
        json=_table_payload(ids["retail_branch"]),
    ).status_code == 403

    assert client.get("/api/cafe/tables", headers=cafe_order_headers).status_code == 200
    assert client.post(
        "/api/cafe/tables",
        headers=cafe_order_headers,
        json=_table_payload(ids["cafe_branch"]),
    ).status_code == 403


def test_table_update_is_versioned(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_p5_test_data(db_session_factory)
    headers = login_headers(client, "cafe.admin@example.test")
    created = client.post(
        "/api/cafe/tables",
        headers=headers,
        json=_table_payload(ids["cafe_branch"], "T02"),
    ).json()

    update = client.put(
        f"/api/cafe/tables/{created['id']}",
        headers=headers,
        json={
            **_table_payload(ids["cafe_branch"], "T02"),
            "display_name": "Window Table",
            "area": "Window",
            "expected_version": created["version"],
        },
    )
    assert update.status_code == 200, update.text
    assert update.json()["version"] == created["version"] + 1

    stale = client.put(
        f"/api/cafe/tables/{created['id']}",
        headers=headers,
        json={
            **_table_payload(ids["cafe_branch"], "T02"),
            "expected_version": created["version"],
        },
    )
    assert stale.status_code == 409
