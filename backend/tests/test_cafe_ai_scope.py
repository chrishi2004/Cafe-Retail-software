from __future__ import annotations

from tests.p9_fixtures import login_headers, seed_p9


def test_cafe_ai_is_database_backed_and_cannot_compare_retail(client, db_session_factory):
    seed_p9(db_session_factory)
    headers = login_headers(client, "cafe.admin@example.test")

    response = client.post("/api/ai/chat", json={"message": "Compare Cafe with Retail today"}, headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["intent"] == "cafe_scope_denied"
    assert "Retail" not in payload["response"]
    assert payload["tool_calls"][0]["data"]["allowed"] is False

    sales = client.post("/api/ai/chat", json={"message": "What are today's Cafe billed sales?"}, headers=headers)
    assert sales.status_code == 200
    assert sales.json()["intent"] == "get_cafe_sales_summary"
    assert sales.json()["tool_calls"][0]["data"]["scope"] == "cafe"
