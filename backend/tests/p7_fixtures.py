from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from tests.multi_venture_fixtures import login_headers
from tests.p6_fixtures import seed_p6_public_ordering


def seed_p7(factory: sessionmaker[Session]) -> dict[str, object]:
    return seed_p6_public_ordering(factory)


def cafe_headers(client: TestClient, role: str) -> dict[str, str]:
    emails = {
        "admin": "cafe.admin@example.test",
        "manager": "cafe.manager@example.test",
        "order_taker": "cafe.orders@example.test",
        "kitchen": "cafe.kitchen@example.test",
        "analyst": "cafe.analyst@example.test",
        "retail_admin": "admin@hybridretail.test",
    }
    return login_headers(client, emails[role])


def create_staff_dine_in_order(
    client: TestClient,
    ids: dict[str, object],
    *,
    headers: dict[str, str] | None = None,
    quantity: int = 1,
):
    headers = headers or cafe_headers(client, "order_taker")
    return client.post(
        "/api/cafe/orders",
        headers=headers,
        json={
            "order_type": "dine_in",
            "branch_id": ids["cafe_branch"],
            "table_session_public_id": ids["table_session_public_id"],
            "items": [
                {
                    "menu_item_public_id": ids["menu_item_public_id"],
                    "quantity": quantity,
                    "notes": "Less sugar",
                }
            ],
            "customer_notes": "Staff entry",
        },
    )


def create_public_order(client: TestClient, ids: dict[str, object], *, key: str = "p7-qr-order-0001"):
    resolved = client.post(f"/api/public/cafe/qr/{ids['raw_qr']}/resolve")
    assert resolved.status_code == 200, resolved.text
    body = resolved.json()
    return client.post(
        f"/api/public/cafe/sessions/{body['session_public_id']}/orders",
        headers={"X-Guest-Access": body["guest_access"], "Idempotency-Key": key},
        json={
            "items": [
                {
                    "menu_item_public_id": ids["menu_item_public_id"],
                    "quantity": 1,
                }
            ]
        },
    )
