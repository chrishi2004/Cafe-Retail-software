from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import AuditLog


def login(client, email: str = "admin@hybridretail.test") -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "RetailDemo@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_category(client, headers: dict[str, str], name: str = "Grocery") -> dict:
    response = client.post(
        "/api/categories",
        json={"name": name, "description": "Packaged food"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def create_supplier(client, headers: dict[str, str], name: str = "FreshLine") -> dict:
    response = client.post(
        "/api/suppliers",
        json={
            "name": name,
            "contact_person": "Kavita Shah",
            "email": "freshline@example.com",
            "phone": "9876500101",
            "address": "Commerce Park",
            "payment_terms": "Net 15",
            "lead_time_days": 3,
            "is_active": True,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def product_payload(category_id: int, supplier_id: int, sku: str = "RICE-5KG") -> dict:
    return {
        "sku": sku,
        "name": "Rice Premium 5kg",
        "description": "Premium packed rice",
        "category_id": category_id,
        "supplier_id": supplier_id,
        "unit_cost": "360.00",
        "selling_price": "485.00",
        "reorder_threshold": "40.00",
        "target_stock_level": "180.00",
        "is_active": True,
    }


def test_admin_can_create_and_edit_supplier(client) -> None:
    headers = login(client)
    supplier = create_supplier(client, headers)

    update_response = client.put(
        f"/api/suppliers/{supplier['id']}",
        json={
            **supplier,
            "name": "FreshLine Distributors",
            "lead_time_days": 5,
        },
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "FreshLine Distributors"
    assert update_response.json()["lead_time_days"] == 5


def test_admin_can_create_and_edit_product(client) -> None:
    headers = login(client)
    category = create_category(client, headers)
    supplier = create_supplier(client, headers)

    create_response = client.post(
        "/api/products",
        json=product_payload(category["id"], supplier["id"]),
        headers=headers,
    )

    assert create_response.status_code == 201
    product = create_response.json()
    assert product["sku"] == "RICE-5KG"
    assert product["category_name"] == "Grocery"
    assert product["supplier_name"] == "FreshLine"

    update_response = client.put(
        f"/api/products/{product['id']}",
        json={
            **product_payload(category["id"], supplier["id"], sku="RICE-5KG"),
            "name": "Rice Premium Family Pack",
            "selling_price": "499.00",
        },
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Rice Premium Family Pack"
    assert update_response.json()["selling_price"] == "499.00"


def test_product_sku_uniqueness_is_enforced(client) -> None:
    headers = login(client)
    category = create_category(client, headers)
    supplier = create_supplier(client, headers)
    payload = product_payload(category["id"], supplier["id"], sku="UNIQUE-001")

    first_response = client.post("/api/products", json=payload, headers=headers)
    duplicate_response = client.post("/api/products", json=payload, headers=headers)

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["error"]["message"] == "Product SKU already exists."


def test_products_default_to_active_records(client) -> None:
    headers = login(client)
    category = create_category(client, headers)
    supplier = create_supplier(client, headers)
    active_product = client.post(
        "/api/products",
        json=product_payload(category["id"], supplier["id"], sku="ACTIVE-001"),
        headers=headers,
    ).json()
    inactive_product = client.post(
        "/api/products",
        json=product_payload(category["id"], supplier["id"], sku="INACTIVE-001"),
        headers=headers,
    ).json()

    deactivate_response = client.patch(
        f"/api/products/{inactive_product['id']}/deactivate",
        headers=headers,
    )
    default_list = client.get("/api/products", headers=headers).json()
    full_list = client.get("/api/products?include_inactive=true", headers=headers).json()

    assert deactivate_response.status_code == 200
    assert [product["sku"] for product in default_list] == [active_product["sku"]]
    assert {product["sku"] for product in full_list} == {"ACTIVE-001", "INACTIVE-001"}


def test_non_admin_cannot_create_or_update_master_data(client) -> None:
    manager_headers = login(client, email="manager@hybridretail.test")

    create_response = client.post(
        "/api/categories",
        json={"name": "Blocked", "description": None},
        headers=manager_headers,
    )

    assert create_response.status_code == 403
    assert create_response.json()["error"]["code"] == "forbidden"


def test_authenticated_users_can_read_master_data(client) -> None:
    admin_headers = login(client)
    category = create_category(client, admin_headers)

    analyst_headers = login(client, email="analyst@hybridretail.test")
    response = client.get("/api/categories", headers=analyst_headers)

    assert response.status_code == 200
    assert response.json()[0]["id"] == category["id"]


def test_admin_can_create_and_update_branches(client) -> None:
    headers = login(client)

    create_response = client.post(
        "/api/branches",
        json={
            "name": "Southside Daily",
            "address": "12 Station Road",
            "city": "Chennai",
            "manager_name": "Isha Menon",
            "is_active": True,
        },
        headers=headers,
    )
    branch = create_response.json()
    update_response = client.put(
        f"/api/branches/{branch['id']}",
        json={**branch, "manager_name": "Isha Raman"},
        headers=headers,
    )

    assert create_response.status_code == 201
    assert update_response.status_code == 200
    assert update_response.json()["manager_name"] == "Isha Raman"


def test_master_data_changes_are_audited(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    headers = login(client)
    create_category(client, headers, name="Audited Category")

    with db_session_factory() as db:
        audit = db.scalar(
            select(AuditLog).where(AuditLog.action == "category.create")
        )

    assert audit is not None
    assert audit.entity_type == "category"
