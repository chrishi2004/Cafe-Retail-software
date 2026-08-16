from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import AuditLog, CafeOrderStatusHistory
from tests.p7_fixtures import cafe_headers, create_staff_dine_in_order, seed_p7


def _act(client, headers, public_id, action, version, reason=None):
    body = {"expected_version": version}
    if reason is not None:
        body["reason"] = reason
    return client.post(f"/api/cafe/orders/{public_id}/{action}", headers=headers, json=body)


def test_valid_order_state_machine_and_history(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p7(db_session_factory)
    staff_headers = cafe_headers(client, "order_taker")
    created = create_staff_dine_in_order(client, ids, headers=staff_headers)
    assert created.status_code == 201, created.text
    order = created.json()

    for action, expected in (
        ("accept", "accepted"),
        ("start-preparing", "preparing"),
        ("mark-ready", "ready"),
        ("serve", "served"),
    ):
        response = _act(client, staff_headers, order["public_id"], action, order["version"])
        assert response.status_code == 200, response.text
        order = response.json()
        assert order["status"] == expected

    session = client.get(f"/api/cafe/table-sessions/{order['table_session_public_id']}", headers=staff_headers)
    assert session.status_code == 200, session.text
    bill = client.post(
        f"/api/cafe/table-sessions/{order['table_session_public_id']}/request-bill",
        headers=staff_headers,
        json={"expected_version": session.json()["version"]},
    )
    assert bill.status_code == 200, bill.text
    assert bill.json()["status"] == "bill_requested"
    assert bill.json()["affected_order_public_ids"] == [order["public_id"]]

    refreshed = client.get(f"/api/cafe/orders/{order['public_id']}", headers=staff_headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "bill_requested"

    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CafeOrderStatusHistory)) == 6
        assert db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.entity_type == "cafe_order")
        ) >= 5
        assert db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.entity_type == "table_session")
        ) >= 1


def test_invalid_state_jump_is_rejected(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p7(db_session_factory)
    headers = cafe_headers(client, "order_taker")
    created = create_staff_dine_in_order(client, ids, headers=headers).json()
    response = _act(client, headers, created["public_id"], "mark-ready", created["version"])
    assert response.status_code == 409
    assert client.patch(
        f"/api/cafe/orders/{created['public_id']}", headers=headers, json={"status": "served"}
    ).status_code in {404, 405}


def test_reject_and_cancel_require_reason_and_are_audited(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p7(db_session_factory)
    headers = cafe_headers(client, "order_taker")

    reject_order = create_staff_dine_in_order(client, ids, headers=headers).json()
    missing = _act(client, headers, reject_order["public_id"], "reject", reject_order["version"])
    assert missing.status_code == 422
    rejected = _act(client, headers, reject_order["public_id"], "reject", reject_order["version"], "Item unavailable")
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"

    cancel_order = create_staff_dine_in_order(client, ids, headers=headers).json()
    cancelled = _act(client, headers, cancel_order["public_id"], "cancel", cancel_order["version"], "Customer changed mind")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    with db_session_factory() as db:
        reasons = set(
            db.scalars(
                select(CafeOrderStatusHistory.reason).where(
                    CafeOrderStatusHistory.reason.in_(["Item unavailable", "Customer changed mind"])
                )
            ).all()
        )
        assert reasons == {"Item unavailable", "Customer changed mind"}


def test_order_taker_cannot_cancel_after_acceptance_but_manager_can(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p7(db_session_factory)
    taker = cafe_headers(client, "order_taker")
    manager = cafe_headers(client, "manager")
    created = create_staff_dine_in_order(client, ids, headers=taker).json()
    accepted = _act(client, taker, created["public_id"], "accept", created["version"]).json()

    denied = _act(client, taker, created["public_id"], "cancel", accepted["version"], "Manager approval required")
    assert denied.status_code == 403

    allowed = _act(client, manager, created["public_id"], "cancel", accepted["version"], "Operational cancellation")
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["status"] == "cancelled"
