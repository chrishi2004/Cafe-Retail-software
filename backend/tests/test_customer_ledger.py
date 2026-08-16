from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Branch, CustomerLedgerEntry, CustomerPayment
from app.services.customers import validate_customer_credit_limit


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


def customer_payload(branch_id: int, opening_balance: str = "1000.00", credit_limit: str = "1500.00") -> dict:
    return {
        "name": "Credit Customer",
        "phone": "9876630001",
        "email": "credit.customer@example.com",
        "gstin": None,
        "billing_address": "21 Ledger Street",
        "shipping_address": "21 Ledger Street",
        "city": "Bengaluru",
        "state": "Karnataka",
        "state_code": "29",
        "pincode": "560001",
        "branch_id": branch_id,
        "company_id": None,
        "credit_limit": credit_limit,
        "opening_balance": opening_balance,
        "is_active": True,
    }


def create_customer(client, headers: dict[str, str], branch_id: int, opening_balance: str = "1000.00", credit_limit: str = "1500.00") -> dict:
    response = client.post(
        "/api/customers",
        json=customer_payload(branch_id, opening_balance=opening_balance, credit_limit=credit_limit),
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_customer_payment_creates_credit_ledger_and_updates_outstanding(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    headers = login(client)
    branch_id = central_branch_id(db_session_factory)
    customer = create_customer(client, headers, branch_id)

    payment_response = client.post(
        f"/api/customers/{customer['id']}/payments",
        json={
            "amount": "250.00",
            "branch_id": branch_id,
            "payment_mode_id": None,
            "reference_number": "RCPT-001",
            "notes": "Partial collection",
        },
        headers=headers,
    )
    ledger_response = client.get(f"/api/customers/{customer['id']}/ledger", headers=headers)
    outstanding_response = client.get("/api/customer-ledger/outstanding", headers=headers)

    assert payment_response.status_code == 201
    assert payment_response.json()["amount"] == "250.00"
    assert payment_response.json()["outstanding_balance"] == "750.00"
    assert ledger_response.status_code == 200
    ledger = ledger_response.json()
    assert [entry["entry_type"] for entry in ledger] == ["opening_balance", "payment"]
    assert [entry["running_balance"] for entry in ledger] == ["1000.00", "750.00"]
    assert outstanding_response.status_code == 200
    assert outstanding_response.json()[0]["outstanding_balance"] == "750.00"

    with db_session_factory() as db:
        payment = db.scalar(select(CustomerPayment).where(CustomerPayment.customer_id == customer["id"]))
        payment_entry = db.scalar(
            select(CustomerLedgerEntry).where(CustomerLedgerEntry.entry_type == "payment")
        )

    assert payment is not None
    assert payment_entry is not None
    assert payment.ledger_entry_id == payment_entry.id


def test_staff_can_record_payment_for_assigned_branch_customer(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    branch_id = central_branch_id(db_session_factory)
    customer = create_customer(client, login(client), branch_id)

    response = client.post(
        f"/api/customers/{customer['id']}/payments",
        json={"amount": "100.00", "branch_id": None, "payment_mode_id": None},
        headers=login(client, email="staff@hybridretail.test"),
    )

    assert response.status_code == 201
    assert response.json()["branch_id"] == branch_id


def test_analyst_cannot_record_customer_payment(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    branch_id = central_branch_id(db_session_factory)
    customer = create_customer(client, login(client), branch_id)

    response = client.post(
        f"/api/customers/{customer['id']}/payments",
        json={"amount": "100.00", "branch_id": branch_id, "payment_mode_id": None},
        headers=login(client, email="analyst@hybridretail.test"),
    )

    assert response.status_code == 403


def test_payment_amount_must_be_positive(client, db_session_factory: sessionmaker[Session]) -> None:
    branch_id = central_branch_id(db_session_factory)
    customer = create_customer(client, login(client), branch_id)

    response = client.post(
        f"/api/customers/{customer['id']}/payments",
        json={"amount": "0.00", "branch_id": branch_id, "payment_mode_id": None},
        headers=login(client),
    )

    assert response.status_code == 422


def test_credit_limit_helper_blocks_projected_over_limit(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    branch_id = central_branch_id(db_session_factory)
    customer = create_customer(client, login(client), branch_id, opening_balance="900.00", credit_limit="1000.00")

    with db_session_factory() as db:
        projected_ok = validate_customer_credit_limit(
            db,
            customer_id=customer["id"],
            additional_debit=Decimal("50.00"),
        )
        with pytest.raises(HTTPException) as exc_info:
            validate_customer_credit_limit(
                db,
                customer_id=customer["id"],
                additional_debit=Decimal("200.00"),
            )

    assert projected_ok == Decimal("950.00")
    assert exc_info.value.status_code == 400
    assert "Credit limit exceeded" in exc_info.value.detail["message"]


def test_customer_ledger_outstanding_can_include_zero_balances(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    branch_id = central_branch_id(db_session_factory)
    customer = create_customer(client, login(client), branch_id, opening_balance="0.00", credit_limit="1000.00")

    default_response = client.get("/api/customer-ledger/outstanding", headers=login(client))
    include_zero_response = client.get("/api/customer-ledger/outstanding?include_zero=true", headers=login(client))

    assert default_response.status_code == 200
    assert customer["id"] not in {row["customer_id"] for row in default_response.json()}
    assert customer["id"] in {row["customer_id"] for row in include_zero_response.json()}
