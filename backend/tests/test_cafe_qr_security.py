from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import AuditLog, TableQRToken
from tests.multi_venture_fixtures import login_headers
from tests.p5_fixtures import seed_p5_test_data


def _create_table(client, headers: dict[str, str], branch_id: int) -> dict:
    response = client.post(
        "/api/cafe/tables",
        headers=headers,
        json={
            "branch_id": branch_id,
            "table_code": "QR01",
            "display_name": "QR Table",
            "capacity": 4,
            "area": "Indoor",
            "is_active": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _decode_urlsafe(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def test_qr_secret_has_256_bits_and_only_hash_is_stored(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p5_test_data(db_session_factory)
    headers = login_headers(client, "cafe.admin@example.test")
    table = _create_table(client, headers, ids["cafe_branch"])

    rotated = client.post(
        f"/api/cafe/tables/{table['id']}/qr/rotate",
        headers=headers,
        json={"expires_in_days": 30, "public_base_url": "/order"},
    )
    assert rotated.status_code == 200, rotated.text
    body = rotated.json()
    assert "token_hash" not in body
    raw_token = body["raw_token"]
    public_reference, secret = raw_token.split(".", 1)
    assert public_reference == body["public_reference"]
    assert len(_decode_urlsafe(secret)) == 32

    with db_session_factory() as db:
        stored = db.scalar(select(TableQRToken).where(TableQRToken.public_reference == public_reference))
        assert stored is not None
        assert stored.token_hash == hashlib.sha256(secret.encode("utf-8")).hexdigest()
        assert stored.token_hash != raw_token
        assert stored.token_hash != secret
        assert stored.token_prefix == secret[:10]
        audit = db.scalar(
            select(AuditLog)
            .where(AuditLog.action == "cafe.table_qr.rotated")
            .order_by(AuditLog.id.desc())
        )
        assert audit is not None
        audit_json = json.dumps(audit.new_value_json)
        assert raw_token not in audit_json
        assert secret not in audit_json

    status_response = client.get(f"/api/cafe/tables/{table['id']}/qr/status", headers=headers)
    assert status_response.status_code == 200
    assert "token_hash" not in status_response.text
    assert "raw_token" not in status_response.text

    print_response = client.post(
        f"/api/cafe/tables/{table['id']}/qr/print-data",
        headers=headers,
        json={"raw_token": raw_token, "public_base_url": "https://example.com/order"},
    )
    assert print_response.status_code == 200, print_response.text
    assert print_response.json()["public_reference"] == public_reference
    assert "token_hash" not in print_response.text
    assert "raw_token" not in print_response.json()
    assert "qr_payload" not in print_response.json()


def test_rotation_revocation_and_expiry_fail_closed(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p5_test_data(db_session_factory)
    headers = login_headers(client, "cafe.admin@example.test")
    table = _create_table(client, headers, ids["cafe_branch"])

    first = client.post(
        f"/api/cafe/tables/{table['id']}/qr/rotate",
        headers=headers,
        json={"expires_in_days": 30, "public_base_url": "/order"},
    ).json()
    first_raw = first["raw_token"]
    assert client.post(f"/api/public/cafe/qr/{first_raw}/resolve").status_code == 200

    second_response = client.post(
        f"/api/cafe/tables/{table['id']}/qr/rotate",
        headers=headers,
        json={"expires_in_days": 30, "public_base_url": "/order"},
    )
    assert second_response.status_code == 200
    second = second_response.json()
    second_raw = second["raw_token"]

    assert client.post(f"/api/public/cafe/qr/{first_raw}/resolve").status_code == 404
    assert client.post(f"/api/public/cafe/qr/{second_raw}/resolve").status_code == 200

    revoked = client.post(f"/api/cafe/tables/{table['id']}/qr/revoke", headers=headers)
    assert revoked.status_code == 200
    assert client.post(f"/api/public/cafe/qr/{second_raw}/resolve").status_code == 404

    third = client.post(
        f"/api/cafe/tables/{table['id']}/qr/rotate",
        headers=headers,
        json={"expires_in_days": 1, "public_base_url": "/order"},
    ).json()
    third_raw = third["raw_token"]
    with db_session_factory() as db:
        token = db.scalar(
            select(TableQRToken).where(TableQRToken.public_reference == third["public_reference"])
        )
        assert token is not None
        token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    expired = client.post(f"/api/public/cafe/qr/{third_raw}/resolve")
    assert expired.status_code == 404
    assert "invalid, expired, or revoked" in expired.json()["error"]["message"].lower()


def test_retail_cannot_rotate_or_read_cafe_qr(client, db_session_factory: sessionmaker[Session]) -> None:
    ids = seed_p5_test_data(db_session_factory)
    cafe_headers = login_headers(client, "cafe.admin@example.test")
    table = _create_table(client, cafe_headers, ids["cafe_branch"])
    retail_headers = login_headers(client, "admin@hybridretail.test")

    assert client.post(
        f"/api/cafe/tables/{table['id']}/qr/rotate",
        headers=retail_headers,
        json={"expires_in_days": 30, "public_base_url": "/order"},
    ).status_code == 403
    assert client.get(f"/api/cafe/tables/{table['id']}/qr/status", headers=retail_headers).status_code == 403
