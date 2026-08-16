from sqlalchemy.orm import Session, sessionmaker

from tests.multi_venture_fixtures import login_headers
from tests.p5_fixtures import seed_p5_test_data


def test_authenticated_qr_render_returns_local_svg_without_hash(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p5_test_data(db_session_factory)
    headers = login_headers(client, "cafe.admin@example.test")
    table_response = client.post(
        "/api/cafe/tables",
        headers=headers,
        json={
            "branch_id": ids["cafe_branch"],
            "table_code": "SVG01",
            "display_name": "SVG Table",
            "capacity": 2,
            "area": "Indoor",
            "is_active": True,
        },
    )
    assert table_response.status_code == 201
    table = table_response.json()

    rotation = client.post(
        f"/api/cafe/tables/{table['id']}/qr/rotate",
        headers=headers,
        json={"expires_in_days": 30, "public_base_url": "/order"},
    )
    assert rotation.status_code == 200
    qr_value = rotation.json()["raw_token"]

    rendered = client.post(
        f"/api/cafe/tables/{table['id']}/qr/render",
        headers=headers,
        json={"raw_token": qr_value, "public_base_url": "/order"},
    )
    assert rendered.status_code == 200, rendered.text
    body = rendered.json()
    assert body["qr_svg_data_uri"].startswith("data:image/svg+xml")
    assert "token_hash" not in rendered.text
    assert "raw_token" not in body
    assert "qr_payload" not in body

    retail_headers = login_headers(client, "admin@hybridretail.test")
    denied = client.post(
        f"/api/cafe/tables/{table['id']}/qr/render",
        headers=retail_headers,
        json={"raw_token": qr_value, "public_base_url": "/order"},
    )
    assert denied.status_code == 403
