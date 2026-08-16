from sqlalchemy.orm import Session, sessionmaker

from tests.p7_fixtures import cafe_headers, create_staff_dine_in_order, seed_p7


def test_two_actors_using_same_order_version_get_one_success_and_one_stale_conflict(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p7(db_session_factory)
    taker = cafe_headers(client, "order_taker")
    manager = cafe_headers(client, "manager")
    created_response = create_staff_dine_in_order(client, ids, headers=taker)
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    version = created["version"]

    first = client.post(
        f"/api/cafe/orders/{created['public_id']}/accept",
        headers=taker,
        json={"expected_version": version},
    )
    assert first.status_code == 200, first.text
    assert first.json()["version"] == version + 1

    stale = client.post(
        f"/api/cafe/orders/{created['public_id']}/reject",
        headers=manager,
        json={"expected_version": version, "reason": "Competing terminal action"},
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["error"]["code"] == "stale_state"

    refreshed = client.get(f"/api/cafe/orders/{created['public_id']}", headers=taker)
    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "accepted"
    assert refreshed.json()["version"] == version + 1
