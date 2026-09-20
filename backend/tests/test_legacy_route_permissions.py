from tests.p7_fixtures import cafe_headers
from tests.p8_fixtures import seed_p8


def test_kitchen_cannot_read_legacy_business_data(client, db_session_factory):
    seed_p8(db_session_factory)
    headers = cafe_headers(client, 'kitchen')
    for path in ('/invoices', '/invoices/1', '/sales', '/sales/summary', '/inventory',
                 '/inventory/movements', '/purchase-orders', '/customers', '/customers/outstanding',
                 '/products', '/suppliers', '/categories', '/branches', '/payment-modes'):
        response = client.get('/api' + path, headers=headers)
        assert response.status_code == 403, (path, response.status_code, response.text)


def test_order_taker_billing_reads_do_not_grant_retail_reporting(client, db_session_factory):
    seed_p8(db_session_factory)
    headers = cafe_headers(client, 'order_taker')
    for path in ('/sales', '/inventory', '/purchase-orders'):
        assert client.get('/api' + path, headers=headers).status_code == 403
    for path in ('/invoices', '/customers', '/payment-modes'):
        response = client.get('/api' + path, headers=headers)
        assert response.status_code == 200, response.text


def test_analyst_keeps_read_access(client, db_session_factory):
    seed_p8(db_session_factory)
    headers = cafe_headers(client, 'analyst')
    for path in ('/invoices', '/sales', '/inventory', '/purchase-orders'):
        response = client.get('/api' + path, headers=headers)
        assert response.status_code == 200, response.text
