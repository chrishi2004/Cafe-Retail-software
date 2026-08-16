from sqlalchemy.orm import Session, sessionmaker

from tests.multi_venture_fixtures import login_headers, seed_two_ventures


def _names(response) -> set[str]:
    assert response.status_code == 200, response.text
    return {row["name"] for row in response.json()}


def test_cafe_admin_cannot_list_or_fetch_retail_master_data(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_two_ventures(db_session_factory)
    headers = login_headers(client, "cafe.admin@example.test")

    products = client.get("/api/products", headers=headers)
    assert products.status_code == 200
    assert {row["name"] for row in products.json()} == {"Cafe Product"}
    assert "Retail Secret Product" not in products.text

    assert _names(client.get("/api/categories", headers=headers)) == {"Shared Category"}
    assert _names(client.get("/api/suppliers", headers=headers)) == {"Shared Supplier"}
    assert _names(client.get("/api/branches", headers=headers)) == {"Cafe Main"}

    detail = client.get(f"/api/products/{ids['retail_product']}", headers=headers)
    assert detail.status_code == 404
    assert "Retail Secret Product" not in detail.text


def test_retail_admin_cannot_discover_cafe_rows(client, db_session_factory: sessionmaker[Session]) -> None:
    seed_two_ventures(db_session_factory)
    headers = login_headers(client, "admin@hybridretail.test")

    products = client.get("/api/products", headers=headers)
    assert products.status_code == 200
    assert {row["name"] for row in products.json()} == {"Retail Secret Product"}
    assert "Cafe Product" not in products.text

    branches = client.get("/api/branches", headers=headers)
    assert branches.status_code == 200
    branch_names = {row["name"] for row in branches.json()}
    assert "Cafe Main" not in branch_names
    assert "Central Market" in branch_names
    assert "Retail North" in branch_names


def test_super_admin_is_the_only_global_scope(client, db_session_factory: sessionmaker[Session]) -> None:
    seed_two_ventures(db_session_factory)
    headers = login_headers(client, "owner@example.test")

    products = client.get("/api/products", headers=headers)
    assert products.status_code == 200
    assert {row["name"] for row in products.json()} == {"Retail Secret Product", "Cafe Product"}

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == "super_admin"
    assert me.json()["company_id"] is None


def test_branch_user_cannot_list_other_branch(client, db_session_factory: sessionmaker[Session]) -> None:
    seed_two_ventures(db_session_factory)
    headers = login_headers(client, "manager@hybridretail.test")

    branches = client.get("/api/branches", headers=headers)
    assert branches.status_code == 200
    assert {row["name"] for row in branches.json()} == {"Central Market"}


def test_cross_company_foreign_ids_fail_without_disclosing_retail_object(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_two_ventures(db_session_factory)
    headers = login_headers(client, "cafe.admin@example.test")

    response = client.post(
        "/api/products",
        headers=headers,
        json={
            "sku": "CAFE-INVALID-REF",
            "name": "Cross Scope Attempt",
            "category_id": ids["retail_category"],
            "supplier_id": ids["retail_supplier"],
            "unit_cost": "10.00",
            "selling_price": "20.00",
        },
    )
    assert response.status_code == 404
    assert "Retail" not in response.text


def test_inventory_list_is_company_scoped(client, db_session_factory: sessionmaker[Session]) -> None:
    seed_two_ventures(db_session_factory)
    cafe_headers = login_headers(client, "cafe.admin@example.test")
    retail_headers = login_headers(client, "admin@hybridretail.test")

    cafe_inventory = client.get("/api/inventory", headers=cafe_headers)
    retail_inventory = client.get("/api/inventory", headers=retail_headers)
    assert cafe_inventory.status_code == 200
    assert retail_inventory.status_code == 200
    assert {row["product_name"] for row in cafe_inventory.json()} == {"Cafe Product"}
    assert {row["product_name"] for row in retail_inventory.json()} == {"Retail Secret Product"}
