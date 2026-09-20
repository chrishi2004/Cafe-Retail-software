from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import ExpenseCategory, ExpenseEntry
from tests.invoice_test_utils import login, setup_invoice_data


def test_expense_posting_summary_and_idempotency(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = setup_invoice_data(client, db_session_factory)
    headers = login(client)
    category = client.post("/api/expenses/categories", headers=headers, json={"name": "Utilities"})
    assert category.status_code == 201
    payload = {"branch_id": ids["branch_id"], "category_id": category.json()["id"], "expense_date": "2026-09-20", "amount": "125.50", "payment_mode": "cash", "vendor_name": "Power Co", "reason": "Monthly electricity", "idempotency_key": "expense-test-001"}
    response = client.post("/api/expenses", headers=headers, json=payload)
    duplicate = client.post("/api/expenses", headers=headers, json=payload)
    summary = client.get("/api/expenses/summary?start_date=2026-09-01&end_date=2026-09-30", headers=headers)
    assert response.status_code == 201, response.text
    assert duplicate.json()["id"] == response.json()["id"]
    assert summary.status_code == 200
    assert summary.json()["total_amount"] == "125.50"
    assert summary.json()["by_category"]["Utilities"] == "125.50"
    with db_session_factory() as db:
        assert db.scalar(select(ExpenseCategory).where(ExpenseCategory.name == "Utilities")) is not None
        entry = db.scalar(select(ExpenseEntry))
    assert entry.amount == Decimal("125.50")
