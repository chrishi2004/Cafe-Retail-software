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


def test_owner_writes_require_selected_venture_and_keep_scope(client, db_session_factory):
    from tests.multi_venture_fixtures import login_headers
    ids = seed_p8(db_session_factory)
    owner = login_headers(client, 'owner@example.test')
    payload = {'name': 'Owner created customer', 'branch_id': ids['cafe_branch']}
    assert client.post('/api/customers', headers=owner, json=payload).status_code == 403
    scoped = {**owner, 'X-Venture-Id': str(ids['cafe_company'])}
    result = client.post('/api/customers', headers=scoped, json=payload)
    assert result.status_code == 201, result.text
    assert result.json()['company_id'] == ids['cafe_company']
    adjustment = {'product_id': ids['cafe_product'], 'branch_id': ids['cafe_branch'],
                  'quantity_change': '1.00', 'reason': 'Verified opening correction'}
    result = client.post('/api/inventory/adjustments', headers=scoped, json=adjustment)
    assert result.status_code == 200, result.text
    adjustment['product_id'] = ids['retail_product']
    assert client.post('/api/inventory/adjustments', headers=scoped, json=adjustment).status_code in (403, 404)
