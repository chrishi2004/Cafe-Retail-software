from sqlalchemy.orm import Session, sessionmaker

from app.models import ProductBarcode, ProductPriceHistory


def login(client, email: str = "admin@hybridretail.test") -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "RetailDemo@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_category(client, headers: dict[str, str], name: str = "Indian Retail") -> dict:
    response = client.post(
        "/api/categories",
        json={"name": name, "description": "Retail goods"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def create_supplier(client, headers: dict[str, str], name: str = "Retail Supplier") -> dict:
    response = client.post(
        "/api/suppliers",
        json={
            "name": name,
            "contact_person": "Asha Rao",
            "email": "supplier@example.com",
            "phone": "9876500222",
            "address": "Wholesale Market",
            "payment_terms": "Net 15",
            "lead_time_days": 4,
            "is_active": True,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def create_tax_rate(client, headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/tax-rates",
        json={
            "name": "GST 18%",
            "rate_percent": "18.00",
            "cess_percent": "0.00",
            "description": "Retail GST slab",
            "is_active": True,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def retail_product_payload(category_id: int, supplier_id: int, tax_rate_id: int, sku: str = "SOAP-100") -> dict:
    return {
        "sku": sku,
        "name": "Bath Soap 100g",
        "description": "GST enabled retail item",
        "category_id": category_id,
        "supplier_id": supplier_id,
        "gst_rate_id": tax_rate_id,
        "unit_cost": "24.00",
        "selling_price": "42.00",
        "hsn_sac_code": "3401",
        "cess_rate_percent": "0.00",
        "primary_barcode": "8902026000001",
        "unit_of_measure": "g",
        "mrp": "45.00",
        "brand": "PureCare",
        "manufacturer": "Retail Supplier",
        "item_type": "goods",
        "batch_tracking_enabled": True,
        "serial_tracking_enabled": False,
        "expiry_tracking_enabled": True,
        "reorder_threshold": "20.00",
        "target_stock_level": "100.00",
        "is_active": True,
    }


def setup_retail_dependencies(client) -> tuple[dict[str, str], dict, dict, dict]:
    headers = login(client)
    category = create_category(client, headers)
    supplier = create_supplier(client, headers)
    tax_rate = create_tax_rate(client, headers)
    return headers, category, supplier, tax_rate


def test_admin_can_create_product_with_gst_hsn_mrp_and_barcode(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    headers, category, supplier, tax_rate = setup_retail_dependencies(client)
    payload = retail_product_payload(category["id"], supplier["id"], tax_rate["id"])

    response = client.post("/api/products", json=payload, headers=headers)

    assert response.status_code == 201
    product = response.json()
    assert product["sku"] == "SOAP-100"
    assert product["gst_rate_id"] == tax_rate["id"]
    assert product["gst_rate_name"] == "GST 18%"
    assert product["gst_rate_percent"] == "18.00"
    assert product["hsn_sac_code"] == "3401"
    assert product["primary_barcode"] == "8902026000001"
    assert product["mrp"] == "45.00"
    assert product["unit_of_measure"] == "g"
    assert product["batch_tracking_enabled"] is True
    assert product["expiry_tracking_enabled"] is True

    with db_session_factory() as db:
        barcode = db.query(ProductBarcode).filter_by(product_id=product["id"], is_primary=True).one()
        price_history = db.query(ProductPriceHistory).filter_by(product_id=product["id"]).one()

    assert barcode.barcode == "8902026000001"
    assert str(price_history.new_selling_price) == product["selling_price"]


def test_duplicate_primary_barcode_is_rejected(client) -> None:
    headers, category, supplier, tax_rate = setup_retail_dependencies(client)
    payload = retail_product_payload(category["id"], supplier["id"], tax_rate["id"])

    first_response = client.post("/api/products", json=payload, headers=headers)
    duplicate_response = client.post(
        "/api/products",
        json={**payload, "sku": "SOAP-101"},
        headers=headers,
    )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["error"]["message"] == "Product barcode already exists."


def test_product_search_finds_sku_name_primary_and_alternate_barcode(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    headers, category, supplier, tax_rate = setup_retail_dependencies(client)
    payload = retail_product_payload(category["id"], supplier["id"], tax_rate["id"])
    product = client.post("/api/products", json=payload, headers=headers).json()

    with db_session_factory() as db:
        db.add(
            ProductBarcode(
                product_id=product["id"],
                barcode="ALT-SOAP-100",
                barcode_type="alternate",
                is_primary=False,
                is_active=True,
            )
        )
        db.commit()

    sku_response = client.get("/api/products/search?q=SOAP-100", headers=headers)
    name_response = client.get("/api/products/search?q=Bath%20Soap", headers=headers)
    primary_response = client.get("/api/products/search?q=8902026000001", headers=headers)
    alternate_response = client.get("/api/products/search?q=ALT-SOAP-100", headers=headers)

    assert sku_response.status_code == 200
    assert name_response.status_code == 200
    assert primary_response.status_code == 200
    assert alternate_response.status_code == 200
    assert sku_response.json()[0]["id"] == product["id"]
    assert name_response.json()[0]["id"] == product["id"]
    assert primary_response.json()[0]["id"] == product["id"]
    assert alternate_response.json()[0]["id"] == product["id"]


def test_invalid_gst_rate_is_rejected(client) -> None:
    headers = login(client)
    category = create_category(client, headers)
    supplier = create_supplier(client, headers)
    payload = retail_product_payload(category["id"], supplier["id"], tax_rate_id=9999)

    response = client.post("/api/products", json=payload, headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "GST/tax rate not found."


def test_negative_mrp_is_rejected(client) -> None:
    headers, category, supplier, tax_rate = setup_retail_dependencies(client)
    payload = {
        **retail_product_payload(category["id"], supplier["id"], tax_rate["id"]),
        "mrp": "-1.00",
    }

    response = client.post("/api/products", json=payload, headers=headers)

    assert response.status_code == 422
