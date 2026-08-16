from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import AuditLog, Branch, Customer, CustomerLedgerEntry


def login(client, email: str = "admin@hybridretail.test") -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "RetailDemo@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def central_branch_id(db_session_factory: sessionmaker[Session]) -> int:
    with db_session_factory() as db:
        branch = db.scalar(select(Branch).where(Branch.name == "Central Market"))
        return branch.id


def customer_payload(branch_id: int | None, phone: str = "9876620001", opening_balance: str = "1000.00") -> dict:
    gstin = f"29ABCDE{phone[-4:]}F1Z8"
    return {
        "name": "Asha Retail Customer",
        "phone": phone,
        "email": f"{phone}@example.com",
        "gstin": gstin,
        "billing_address": "12 Customer Street",
        "shipping_address": "12 Customer Street",
        "city": "Bengaluru",
        "state": "Karnataka",
        "state_code": "29",
        "pincode": "560001",
        "branch_id": branch_id,
        "company_id": None,
        "credit_limit": "5000.00",
        "opening_balance": opening_balance,
        "is_active": True,
    }


def create_customer(client, headers: dict[str, str], branch_id: int | None, phone: str = "9876620001", opening_balance: str = "1000.00") -> dict:
    response = client.post(
        "/api/customers",
        json=customer_payload(branch_id, phone=phone, opening_balance=opening_balance),
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_admin_can_create_edit_and_deactivate_customer(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    headers = login(client)
    branch_id = central_branch_id(db_session_factory)

    customer = create_customer(client, headers, branch_id)

    assert customer["name"] == "Asha Retail Customer"
    assert customer["branch_id"] == branch_id
    assert customer["gstin"] == "29ABCDE0001F1Z8"
    assert customer["outstanding_balance"] == "1000.00"
    assert customer["available_credit"] == "4000.00"
    assert len(customer["addresses"]) == 2

    update_payload = {
        **customer_payload(branch_id),
        "name": "Asha Retail Updated",
        "phone": "9876620099",
        "email": "updated.customer@example.com",
        "gstin": "29ABCDE1234F1Z9",
        "credit_limit": "6000.00",
        "opening_balance": "1250.00",
    }
    update_response = client.put(f"/api/customers/{customer['id']}", json=update_payload, headers=headers)
    deactivate_response = client.patch(f"/api/customers/{customer['id']}/deactivate", headers=headers)

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Asha Retail Updated"
    assert update_response.json()["outstanding_balance"] == "1250.00"
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False

    with db_session_factory() as db:
        ledger_entries = db.scalars(
            select(CustomerLedgerEntry).where(CustomerLedgerEntry.customer_id == customer["id"])
        ).all()
        audit = db.scalar(select(AuditLog).where(AuditLog.action == "customer.create"))

    assert [entry.entry_type.value for entry in ledger_entries] == ["opening_balance", "adjustment"]
    assert audit is not None


def test_manager_can_manage_assigned_branch_customers_only(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    admin_headers = login(client)
    manager_headers = login(client, email="manager@hybridretail.test")
    central_id = central_branch_id(db_session_factory)
    with db_session_factory() as db:
        north = Branch(name="North Branch", city="Delhi", is_active=True)
        db.add(north)
        db.commit()
        north_id = north.id

    assigned_response = client.post(
        "/api/customers",
        json=customer_payload(central_id, phone="9876620002", opening_balance="0.00"),
        headers=manager_headers,
    )
    other_branch_response = client.post(
        "/api/customers",
        json=customer_payload(north_id, phone="9876620003", opening_balance="0.00"),
        headers=manager_headers,
    )
    north_customer = create_customer(client, admin_headers, north_id, phone="9876620004", opening_balance="0.00")
    manager_list = client.get("/api/customers", headers=manager_headers)

    assert assigned_response.status_code == 201
    assert other_branch_response.status_code == 403
    assert north_customer["branch_id"] == north_id
    assert {customer["id"] for customer in manager_list.json()} == {assigned_response.json()["id"]}


def test_staff_and_analyst_cannot_create_customers(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    branch_id = central_branch_id(db_session_factory)
    staff_response = client.post(
        "/api/customers",
        json=customer_payload(branch_id, phone="9876620005"),
        headers=login(client, email="staff@hybridretail.test"),
    )
    analyst_response = client.post(
        "/api/customers",
        json=customer_payload(branch_id, phone="9876620006"),
        headers=login(client, email="analyst@hybridretail.test"),
    )

    assert staff_response.status_code == 403
    assert analyst_response.status_code == 403


def test_customer_search_and_inactive_filter(client, db_session_factory: sessionmaker[Session]) -> None:
    headers = login(client)
    branch_id = central_branch_id(db_session_factory)
    customer = create_customer(client, headers, branch_id, phone="9876620007", opening_balance="0.00")
    client.patch(f"/api/customers/{customer['id']}/deactivate", headers=headers)

    default_list = client.get("/api/customers?search=9876620007", headers=headers)
    inactive_list = client.get("/api/customers?search=9876620007&include_inactive=true", headers=headers)

    assert default_list.status_code == 200
    assert inactive_list.status_code == 200
    assert default_list.json() == []
    assert inactive_list.json()[0]["id"] == customer["id"]


def test_customer_duplicate_phone_is_rejected(client, db_session_factory: sessionmaker[Session]) -> None:
    headers = login(client)
    branch_id = central_branch_id(db_session_factory)
    first = client.post("/api/customers", json=customer_payload(branch_id, phone="9876620008"), headers=headers)
    duplicate = client.post(
        "/api/customers",
        json={**customer_payload(branch_id, phone="9876620008"), "email": "duplicate@example.com", "gstin": "29ABCDE1234F1Y8"},
        headers=headers,
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message"] == "Customer phone, email, or GSTIN already exists."
