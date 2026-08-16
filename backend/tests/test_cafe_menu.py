from sqlalchemy.orm import Session, sessionmaker

from tests.multi_venture_fixtures import login_headers
from tests.p5_fixtures import seed_p5_test_data


def _create_category(client, headers: dict[str, str], name: str = "Hot Beverages") -> dict:
    response = client.post(
        "/api/cafe/menu/categories",
        headers=headers,
        json={"branch_id": None, "name": name, "display_order": 1, "is_active": True},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _item_payload(category_id: int, product_id: int | None, **overrides) -> dict:
    payload = {
        "branch_id": None,
        "category_id": category_id,
        "product_id": product_id,
        "name": "Masala Chai",
        "description": "Freshly brewed",
        "image_reference": None,
        "selling_price": "45.00",
        "preparation_area": "beverage",
        "available": True,
        "is_active": True,
        "display_order": 1,
    }
    payload.update(overrides)
    return payload


def test_cafe_admin_manages_only_cafe_menu(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_p5_test_data(db_session_factory)
    cafe_headers = login_headers(client, "cafe.admin@example.test")
    category = _create_category(client, cafe_headers)

    created = client.post(
        "/api/cafe/menu/items",
        headers=cafe_headers,
        json=_item_payload(category["id"], ids["cafe_product"]),
    )
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["company_id"] == ids["cafe_company"]
    assert item["product_id"] == ids["cafe_product"]
    assert item["preparation_area"] == "beverage"

    listed = client.get("/api/cafe/menu/items", headers=cafe_headers)
    assert listed.status_code == 200
    assert [row["name"] for row in listed.json()] == ["Masala Chai"]

    availability = client.patch(
        f"/api/cafe/menu/items/{item['id']}/availability",
        headers=cafe_headers,
        json={"available": False, "expected_version": item["version"]},
    )
    assert availability.status_code == 200
    assert availability.json()["available"] is False
    assert availability.json()["version"] == item["version"] + 1

    retail_headers = login_headers(client, "admin@hybridretail.test")
    assert client.get("/api/cafe/menu/categories", headers=retail_headers).status_code == 403
    assert client.get("/api/cafe/menu/items", headers=retail_headers).status_code == 403
    assert client.post(
        "/api/cafe/menu/categories",
        headers=retail_headers,
        json={"branch_id": None, "name": "Retail Leak", "display_order": 0, "is_active": True},
    ).status_code == 403


def test_unauthorized_cafe_roles_cannot_administer_menu(client, db_session_factory: sessionmaker[Session]) -> None:
    seed_p5_test_data(db_session_factory)
    order_headers = login_headers(client, "cafe.orders@example.test")
    read_response = client.get("/api/cafe/menu/categories", headers=order_headers)
    assert read_response.status_code == 200

    create_response = client.post(
        "/api/cafe/menu/categories",
        headers=order_headers,
        json={"branch_id": None, "name": "Blocked", "display_order": 0, "is_active": True},
    )
    assert create_response.status_code == 403


def test_retail_product_cannot_link_to_cafe_menu_item(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_p5_test_data(db_session_factory)
    headers = login_headers(client, "cafe.admin@example.test")
    category = _create_category(client, headers)

    response = client.post(
        "/api/cafe/menu/items",
        headers=headers,
        json=_item_payload(category["id"], ids["retail_product"]),
    )
    assert response.status_code == 400
    assert "selected Cafe venture" in response.json()["error"]["message"]


def test_invalid_menu_price_and_preparation_area_fail(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_p5_test_data(db_session_factory)
    headers = login_headers(client, "cafe.admin@example.test")
    category = _create_category(client, headers)

    negative = client.post(
        "/api/cafe/menu/items",
        headers=headers,
        json=_item_payload(category["id"], ids["cafe_product"], selling_price="-1.00"),
    )
    invalid_area = client.post(
        "/api/cafe/menu/items",
        headers=headers,
        json=_item_payload(category["id"], ids["cafe_product"], preparation_area="dishwasher"),
    )
    assert negative.status_code == 422
    assert invalid_area.status_code == 422


def test_company_wide_menu_visible_to_branch_role_without_cross_branch_override(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p5_test_data(db_session_factory)
    admin_headers = login_headers(client, "cafe.admin@example.test")
    global_category = _create_category(client, admin_headers, "Global")
    branch_category_response = client.post(
        "/api/cafe/menu/categories",
        headers=admin_headers,
        json={
            "branch_id": ids["cafe_second_branch"],
            "name": "Annex Only",
            "display_order": 2,
            "is_active": True,
        },
    )
    assert branch_category_response.status_code == 201

    manager_headers = login_headers(client, "cafe.manager@example.test")
    visible = client.get("/api/cafe/menu/categories", headers=manager_headers)
    assert visible.status_code == 200
    assert {row["id"] for row in visible.json()} == {global_category["id"]}
