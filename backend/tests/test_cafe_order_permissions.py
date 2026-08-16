from sqlalchemy.orm import Session, sessionmaker

from tests.p7_fixtures import cafe_headers, create_staff_dine_in_order, seed_p7


def test_kitchen_projection_contains_only_preparation_data_and_allowed_actions(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p7(db_session_factory)
    taker = cafe_headers(client, "order_taker")
    kitchen = cafe_headers(client, "kitchen")
    manager = cafe_headers(client, "manager")

    created = create_staff_dine_in_order(client, ids, headers=taker).json()
    accepted_response = client.post(
        f"/api/cafe/orders/{created['public_id']}/accept",
        headers=taker,
        json={"expected_version": created["version"]},
    )
    assert accepted_response.status_code == 200, accepted_response.text
    accepted = accepted_response.json()

    queue = client.get("/api/cafe/kitchen/orders", headers=kitchen)
    assert queue.status_code == 200, queue.text
    assert len(queue.json()) == 1
    kitchen_order = queue.json()[0]
    assert kitchen_order["public_id"] == created["public_id"]
    serialized = str(kitchen_order).lower()
    for forbidden in (
        "unit_price",
        "subtotal",
        "estimated_total",
        "customer_notes",
        "created_by",
        "payment",
        "tax",
        "margin",
        "cost",
        "company_id",
        "branch_id",
    ):
        assert forbidden not in serialized

    cannot_accept = client.post(
        f"/api/cafe/orders/{created['public_id']}/accept",
        headers=kitchen,
        json={"expected_version": accepted["version"]},
    )
    assert cannot_accept.status_code == 403

    preparing = client.post(
        f"/api/cafe/orders/{created['public_id']}/start-preparing",
        headers=kitchen,
        json={"expected_version": accepted["version"]},
    )
    assert preparing.status_code == 200, preparing.text
    ready = client.post(
        f"/api/cafe/orders/{created['public_id']}/mark-ready",
        headers=kitchen,
        json={"expected_version": preparing.json()["version"]},
    )
    assert ready.status_code == 200, ready.text

    cannot_serve = client.post(
        f"/api/cafe/orders/{created['public_id']}/serve",
        headers=kitchen,
        json={"expected_version": ready.json()["version"]},
    )
    assert cannot_serve.status_code == 403
    served = client.post(
        f"/api/cafe/orders/{created['public_id']}/serve",
        headers=manager,
        json={"expected_version": ready.json()["version"]},
    )
    assert served.status_code == 200, served.text


def test_analyst_is_read_only_and_retail_admin_cannot_use_cafe_order_endpoints(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p7(db_session_factory)
    taker = cafe_headers(client, "order_taker")
    analyst = cafe_headers(client, "analyst")
    retail = cafe_headers(client, "retail_admin")
    created = create_staff_dine_in_order(client, ids, headers=taker)
    assert created.status_code == 201

    assert client.get("/api/cafe/orders", headers=analyst).status_code == 200
    analyst_write = client.post(
        "/api/cafe/orders",
        headers=analyst,
        json={
            "order_type": "takeaway",
            "branch_id": ids["cafe_branch"],
            "items": [{"menu_item_public_id": ids["menu_item_public_id"], "quantity": 1}],
        },
    )
    assert analyst_write.status_code == 403

    assert client.get("/api/cafe/orders", headers=retail).status_code == 403
    retail_write = client.post(
        "/api/cafe/orders",
        headers=retail,
        json={
            "order_type": "takeaway",
            "branch_id": ids["cafe_branch"],
            "items": [{"menu_item_public_id": ids["menu_item_public_id"], "quantity": 1}],
        },
    )
    assert retail_write.status_code == 403


def test_branch_scoped_cafe_user_cannot_cross_branch(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p7(db_session_factory)
    taker = cafe_headers(client, "order_taker")
    response = client.post(
        "/api/cafe/orders",
        headers=taker,
        json={
            "order_type": "takeaway",
            "branch_id": ids["cafe_second_branch"],
            "items": [{"menu_item_public_id": ids["menu_item_public_id"], "quantity": 1}],
        },
    )
    assert response.status_code == 403
