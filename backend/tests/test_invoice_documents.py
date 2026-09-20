from tests.invoice_test_utils import login, setup_invoice_data


def test_issued_invoice_has_printable_html_and_pdf_variants(client, db_session_factory):
    ids = setup_invoice_data(client, db_session_factory)
    headers = login(client, email="staff@hybridretail.test")
    draft = client.post(
        "/api/invoices",
        headers=headers,
        json={
            "branch_id": ids["branch_id"],
            "invoice_type": "non_gst",
            "items": [{"product_id": ids["product_id"], "quantity": "1.00"}],
        },
    )
    assert draft.status_code == 201, draft.text
    invoice_id = draft.json()["id"]
    issued = client.post(
        f"/api/invoices/{invoice_id}/issue",
        headers=headers,
        json={"payments": [{"payment_mode_id": ids["cash_mode_id"], "amount": "100.00"}]},
    )
    assert issued.status_code == 200, issued.text
    invoice_number = issued.json()["invoice_number"]

    html_response = client.get(
        f"/api/invoices/{invoice_id}/document",
        headers=headers,
        params={"format": "html", "template_type": "pos_80mm"},
    )
    assert html_response.status_code == 200, html_response.text
    assert html_response.headers["content-type"].startswith("text/html")
    assert invoice_number in html_response.text
    assert "POS Bath Soap" in html_response.text
    assert "Terms:" in html_response.text

    pdf_response = client.get(
        f"/api/invoices/{invoice_id}/document",
        headers=headers,
        params={"format": "pdf", "template_type": "a4_gst_invoice"},
    )
    assert pdf_response.status_code == 200, pdf_response.text
    assert pdf_response.headers["content-type"].startswith("application/pdf")
    assert pdf_response.content.startswith(b"%PDF-")
    assert invoice_number.encode() in pdf_response.content


def test_draft_and_future_document_types_are_rejected(client, db_session_factory):
    ids = setup_invoice_data(client, db_session_factory)
    headers = login(client)
    draft = client.post(
        "/api/invoices",
        headers=headers,
        json={
            "branch_id": ids["branch_id"],
            "invoice_type": "non_gst",
            "items": [{"product_id": ids["product_id"], "quantity": "1.00"}],
        },
    )
    assert draft.status_code == 201
    response = client.get(f"/api/invoices/{draft.json()['id']}/document", headers=headers)
    assert response.status_code == 400

    response = client.get(
        f"/api/invoices/{draft.json()['id']}/document",
        headers=headers,
        params={"template_type": "credit_note"},
    )
    assert response.status_code == 400
